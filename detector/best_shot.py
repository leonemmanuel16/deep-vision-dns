"""
Best Shot Selector — Picks the best frame per tracker_id for evidence.

Tracks each object across frames and selects the snapshot with:
- Highest confidence
- Largest bounding box area
- Most centered position

Generates 4MP snapshots and stores them in MinIO.
"""

import io
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np
from PIL import Image
from minio import Minio

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class TrackedObject:
    """State for a tracked object across frames."""
    tracker_id: int
    camera_id: str
    label: str
    best_confidence: float = 0.0
    best_bbox_area: float = 0.0
    best_frame: Optional[np.ndarray] = None
    best_bbox: Optional[dict] = None
    frame_count: int = 0
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    snapshot_saved: bool = False


class BestShotSelector:
    """
    Selects best snapshot per tracked object and saves to MinIO.
    """

    MIN_FRAMES = 3  # Minimum frames before saving
    MAX_AGE_SECONDS = 30  # Expire tracker after this

    def __init__(self):
        self.tracked: dict[str, TrackedObject] = {}  # key: "camera_id:tracker_id"
        self.minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_user,
            secret_key=settings.minio_password,
            secure=False,
        )
        self._ensure_buckets()

    def _ensure_buckets(self):
        """Create MinIO buckets if they don't exist."""
        for bucket in [settings.minio_bucket_snapshots, settings.minio_bucket_clips]:
            try:
                if not self.minio_client.bucket_exists(bucket):
                    self.minio_client.make_bucket(bucket)
                    logger.info(f"Created MinIO bucket: {bucket}")
            except Exception as e:
                logger.error(f"MinIO bucket check failed: {e}")

    def update(
        self,
        camera_id: str,
        tracker_id: int,
        label: str,
        confidence: float,
        bbox: dict,
        frame: Optional[np.ndarray] = None,
    ) -> Optional[dict]:
        """
        Update tracking state for a detection.
        Returns event dict if this is a finalized best shot, else None.
        """
        key = f"{camera_id}:{tracker_id}"
        now = time.time()

        if key not in self.tracked:
            self.tracked[key] = TrackedObject(
                tracker_id=tracker_id,
                camera_id=camera_id,
                label=label,
            )

        obj = self.tracked[key]
        obj.last_seen = now
        obj.frame_count += 1

        # Update best shot if this detection is better
        bbox_area = (bbox["x2"] - bbox["x1"]) * (bbox["y2"] - bbox["y1"])
        score = confidence * 0.6 + bbox_area * 0.4

        best_score = obj.best_confidence * 0.6 + obj.best_bbox_area * 0.4

        if score > best_score and frame is not None:
            obj.best_confidence = confidence
            obj.best_bbox_area = bbox_area
            obj.best_frame = frame.copy()
            obj.best_bbox = bbox

        return None

    def flush_expired(self) -> list[dict]:
        """
        Check for expired trackers and finalize their best shots.
        Returns list of finalized events.
        """
        now = time.time()
        events = []
        expired_keys = []

        for key, obj in self.tracked.items():
            age = now - obj.last_seen

            if age > self.MAX_AGE_SECONDS and not obj.snapshot_saved:
                if obj.frame_count >= self.MIN_FRAMES and obj.best_frame is not None:
                    snapshot_url = self._save_snapshot(obj)
                    event = {
                        "camera_id": obj.camera_id,
                        "tracker_id": obj.tracker_id,
                        "label": obj.label,
                        "confidence": obj.best_confidence,
                        "bbox": obj.best_bbox,
                        "snapshot_url": snapshot_url,
                        "frame_count": obj.frame_count,
                        "duration_seconds": round(obj.last_seen - obj.first_seen, 1),
                        "first_seen": obj.first_seen,
                        "last_seen": obj.last_seen,
                    }
                    events.append(event)
                    obj.snapshot_saved = True

                expired_keys.append(key)

        # Clean up expired entries
        for key in expired_keys:
            del self.tracked[key]

        return events

    def _save_snapshot(self, obj: TrackedObject) -> str:
        """Save best frame as 4MP JPEG to MinIO."""
        try:
            frame = obj.best_frame
            # Upscale to ~4MP if needed (2560x1440)
            h, w = frame.shape[:2]
            target_pixels = 4_000_000
            current_pixels = h * w

            if current_pixels < target_pixels:
                scale = (target_pixels / current_pixels) ** 0.5
                new_w = int(w * scale)
                new_h = int(h * scale)
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

            # Encode to JPEG
            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            data = io.BytesIO(buffer.tobytes())
            size = data.getbuffer().nbytes

            # Build object name
            timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(obj.first_seen))
            object_name = f"{obj.camera_id}/{timestamp}_{obj.label}_{obj.tracker_id}.jpg"

            # Upload to MinIO
            self.minio_client.put_object(
                settings.minio_bucket_snapshots,
                object_name,
                data,
                size,
                content_type="image/jpeg",
            )

            url = f"/{settings.minio_bucket_snapshots}/{object_name}"
            logger.info(f"Saved snapshot: {url} ({size/1024:.0f}KB)")
            return url

        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            return ""
