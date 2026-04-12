"""
Nightly Job — Deep Review re-evaluation of events.

Runs in configurable window (default 00:00-05:00):
1. Finds events with needs_deep_review = true
2. Re-processes with higher quality (main stream 4MP)
3. Adds detailed attributes: EPP, clothing, vehicle details
4. Updates events in PostgreSQL
"""

import json
import time
import logging
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
import schedule

from config import settings

logger = logging.getLogger(__name__)


class NightlyReview:
    """
    Deep Review processor — re-evaluates events during off-peak hours
    with more detailed analysis.
    """

    def __init__(self):
        self.db_conn = None
        self._running = False
        self._connect_db()

    def _connect_db(self):
        try:
            self.db_conn = psycopg2.connect(settings.db_url)
            self.db_conn.autocommit = True
        except Exception as e:
            logger.error(f"NightlyReview DB connection failed: {e}")

    def _ensure_db(self):
        if self.db_conn is None or self.db_conn.closed:
            self._connect_db()

    def is_in_window(self) -> bool:
        """Check if current time is within the nightly review window."""
        now = datetime.now()
        return settings.nightly_start_hour <= now.hour < settings.nightly_end_hour

    def get_pending_events(self, batch_size: int = 100) -> list[dict]:
        """Fetch events that need deep review."""
        self._ensure_db()
        try:
            with self.db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT e.id, e.camera_id, e.label, e.confidence, e.bbox,
                           e.tracker_id, e.snapshot_url, e.detected_at,
                           c.rtsp_url, c.rtsp_sub_url
                    FROM events e
                    JOIN cameras c ON e.camera_id = c.id
                    WHERE e.needs_deep_review = true
                    AND e.detected_at > NOW() - INTERVAL '%s hours'
                    ORDER BY e.detected_at DESC
                    LIMIT %s
                    """,
                    (settings.video_retention_hours, batch_size),
                )
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch pending events: {e}")
            return []

    def process_event(self, event: dict) -> dict:
        """
        Re-process a single event with deeper analysis.
        In production, this would run a secondary model on the main stream.
        Returns updated attributes.
        """
        attributes = {}
        label = event.get("label", "")

        if label == "person":
            attributes = self._analyze_person(event)
        elif label in ("car", "truck", "bus", "motorcycle"):
            attributes = self._analyze_vehicle(event)

        return attributes

    def _analyze_person(self, event: dict) -> dict:
        """
        Analyze person attributes using secondary model.
        In production: runs face detection, attribute classification on 4MP crop.
        Stub returns structure for the attributes.
        """
        # TODO: Integrate secondary nvinfer model for attribute classification
        # This would use the main stream (4MP) and crop the person bbox
        # Then run a classification model for:
        return {
            "ropa_sup_tipo": None,      # "camiseta", "camisa", "chamarra"
            "ropa_sup_color": None,     # "azul", "rojo", "negro"
            "ropa_inf_tipo": None,      # "pantalon", "short", "falda"
            "ropa_inf_color": None,     # "negro", "azul", "gris"
            "casco": None,             # true/false
            "chaleco": None,           # true/false
            "mochila": None,           # true/false
            "lentes": None,            # true/false
            "genero_estimado": None,   # "M", "F"
            "edad_estimada": None,     # "20-30", "30-40"
            "face_detected": False,
            "face_match_id": None,
        }

    def _analyze_vehicle(self, event: dict) -> dict:
        """Analyze vehicle attributes."""
        return {
            "tipo_vehiculo": None,     # "sedan", "pickup", "suv", "van"
            "color_vehiculo": None,    # "blanco", "negro", "rojo"
            "placa_detectada": False,
            "placa_texto": None,
            "marca_estimada": None,
            "direccion": None,         # "entrada", "salida"
        }

    def update_event_attributes(self, event_id: str, attributes: dict):
        """Update event with deep review attributes."""
        self._ensure_db()
        try:
            with self.db_conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE events
                    SET attributes = %s,
                        needs_deep_review = false,
                        review_pass = CASE
                            WHEN review_pass = 'online' THEN 'both'
                            ELSE 'nightly'
                        END,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (json.dumps(attributes), event_id),
                )
        except Exception as e:
            logger.error(f"Failed to update event {event_id}: {e}")

    def run_batch(self):
        """Process a batch of pending events."""
        if not self.is_in_window():
            return

        events = self.get_pending_events()
        if not events:
            logger.info("Nightly review: no pending events")
            return

        logger.info(f"Nightly review: processing {len(events)} events")

        for event in events:
            if not self.is_in_window():
                logger.info("Nightly review: window closed, stopping")
                break

            attributes = self.process_event(event)
            self.update_event_attributes(str(event["id"]), attributes)

        logger.info("Nightly review batch complete")

    def schedule_job(self):
        """Schedule nightly review to run every 30 minutes during window."""
        schedule.every(30).minutes.do(self.run_batch)
        logger.info(
            f"Nightly review scheduled: {settings.nightly_start_hour:02d}:00 - "
            f"{settings.nightly_end_hour:02d}:00"
        )
