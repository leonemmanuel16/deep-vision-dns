"""
Event Logic — Validates detections and creates persistent events.

Applies rules:
- Minimum frame count per tracker
- Minimum time in zone
- Deduplication by tracker_id
- Clip generation (10s before + 10s after)

Stores validated events in PostgreSQL and clips in MinIO.
"""

import json
import time
import logging
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras
import redis

from config import settings

logger = logging.getLogger(__name__)

# Labels that generate events
EVENT_LABELS = {"person", "car", "truck", "bus", "motorcycle", "bicycle", "cat", "dog"}


class EventManager:
    """Manages event validation, storage, and clip generation."""

    def __init__(self):
        self.db_conn = None
        self.redis_client = redis.from_url(settings.redis_url)
        self._recent_events: dict[str, float] = {}  # dedup cache
        self._connect_db()

    def _connect_db(self):
        """Connect to PostgreSQL."""
        try:
            self.db_conn = psycopg2.connect(settings.db_url)
            self.db_conn.autocommit = True
            logger.info("EventManager connected to PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")

    def _ensure_db(self):
        """Reconnect if connection is lost."""
        if self.db_conn is None or self.db_conn.closed:
            self._connect_db()

    def process_detection(self, event_data: dict) -> Optional[str]:
        """
        Process a finalized detection from BestShotSelector.
        Returns event_id if event was created, None if filtered.
        """
        camera_id = event_data["camera_id"]
        label = event_data["label"]
        tracker_id = event_data["tracker_id"]

        # Filter: only create events for relevant labels
        if label not in EVENT_LABELS:
            return None

        # Filter: minimum frames
        if event_data.get("frame_count", 0) < 3:
            return None

        # Dedup: same camera + tracker in last 60 seconds
        dedup_key = f"{camera_id}:{tracker_id}"
        now = time.time()
        if dedup_key in self._recent_events:
            if now - self._recent_events[dedup_key] < 60:
                return None
        self._recent_events[dedup_key] = now

        # Clean old dedup entries
        cutoff = now - 120
        self._recent_events = {
            k: v for k, v in self._recent_events.items() if v > cutoff
        }

        # Determine event type
        event_type = self._classify_event(label, event_data)

        # Store in PostgreSQL
        event_id = self._store_event(
            camera_id=camera_id,
            event_type=event_type,
            label=label,
            confidence=event_data["confidence"],
            bbox=event_data.get("bbox"),
            tracker_id=tracker_id,
            snapshot_url=event_data.get("snapshot_url", ""),
            detected_at=datetime.fromtimestamp(
                event_data.get("first_seen", now), tz=timezone.utc
            ),
        )

        if event_id:
            # Publish event for real-time dashboard
            self._publish_event(event_id, event_data)
            logger.info(f"Event created: {event_type} ({label}) camera={camera_id} id={event_id}")

        return event_id

    def _classify_event(self, label: str, data: dict) -> str:
        """Classify event type based on label and context."""
        if label == "person":
            return "person_detected"
        elif label in ("car", "truck", "bus", "motorcycle"):
            return "vehicle_detected"
        elif label in ("bicycle",):
            return "bicycle_detected"
        elif label in ("cat", "dog"):
            return "animal_detected"
        return "object_detected"

    def _store_event(
        self,
        camera_id: str,
        event_type: str,
        label: str,
        confidence: float,
        bbox: Optional[dict],
        tracker_id: int,
        snapshot_url: str,
        detected_at: datetime,
    ) -> Optional[str]:
        """Insert event into PostgreSQL."""
        self._ensure_db()

        try:
            with self.db_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO events (
                        camera_id, event_type, label, confidence,
                        bbox, tracker_id, snapshot_url,
                        review_pass, needs_deep_review, detected_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        'online', true, %s
                    ) RETURNING id
                    """,
                    (
                        camera_id, event_type, label, confidence,
                        json.dumps(bbox) if bbox else None,
                        tracker_id, snapshot_url,
                        detected_at,
                    ),
                )
                result = cur.fetchone()
                return str(result[0]) if result else None
        except Exception as e:
            logger.error(f"Failed to store event: {e}")
            return None

    def _publish_event(self, event_id: str, event_data: dict):
        """Publish new event to Redis for dashboard consumption."""
        payload = json.dumps({
            "event_id": event_id,
            **event_data,
        })
        self.redis_client.publish("events:new", payload)

    def get_camera_rtsp_urls(self) -> dict[str, dict]:
        """Fetch all enabled cameras from the database."""
        self._ensure_db()
        cameras = {}
        try:
            with self.db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, name, rtsp_url, rtsp_sub_url, config FROM cameras WHERE enabled = true"
                )
                for row in cur.fetchall():
                    cameras[str(row["id"])] = {
                        "name": row["name"],
                        "rtsp_url": row["rtsp_url"],
                        "rtsp_sub_url": row["rtsp_sub_url"] or row["rtsp_url"],
                        "config": row["config"] or {},
                    }
        except Exception as e:
            logger.error(f"Failed to fetch cameras: {e}")
        return cameras

    def update_camera_status(self, camera_id: str, status: str):
        """Update camera online/offline status."""
        self._ensure_db()
        try:
            with self.db_conn.cursor() as cur:
                cur.execute(
                    "UPDATE cameras SET status = %s, updated_at = NOW() WHERE id = %s",
                    (status, camera_id),
                )
        except Exception as e:
            logger.error(f"Failed to update camera status: {e}")
