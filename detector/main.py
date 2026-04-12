"""
Deep Vision by DNS — YOLO Detector Service

Lightweight replacement for DeepStream pipeline. Uses Ultralytics YOLOv8
with BoT-SORT tracking, OpenCV RTSP capture, and direct DB/Redis/MinIO
integration.

Flow per camera:
  1. Capture RTSP frames via OpenCV
  2. Every Nth frame, run YOLO inference + tracking on GPU
  3. Deduplicate by tracker_id (30s window)
  4. Publish detections to Redis
  5. Save new events to PostgreSQL
  6. Upload snapshot JPEGs to MinIO
"""

import io
import json
import signal
import logging
import time
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

import cv2
import numpy as np
import psycopg2
import psycopg2.extras
import redis
from minio import Minio
from minio.error import S3Error
from PIL import Image

from config import settings
from yolo_detector import YOLODetector, Detection

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","msg":"%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("detector")


# ────────────────────────────────────────────────────────────
# Database helpers
# ────────────────────────────────────────────────────────────

class DatabaseManager:
    """Thread-safe PostgreSQL manager (one connection per thread)."""

    def __init__(self):
        self._local = threading.local()

    def _get_conn(self) -> psycopg2.extensions.connection:
        conn = getattr(self._local, "conn", None)
        if conn is None or conn.closed:
            conn = psycopg2.connect(settings.db_url)
            conn.autocommit = True
            self._local.conn = conn
        return conn

    def fetch_cameras(self) -> dict:
        """Return {camera_id_str: {name, rtsp_url, ...}} for enabled cameras."""
        conn = self._get_conn()
        cameras = {}
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, name, rtsp_url FROM cameras WHERE enabled = true"
                )
                for row in cur.fetchall():
                    cameras[str(row["id"])] = {
                        "name": row["name"],
                        "rtsp_url": row["rtsp_url"],
                    }
        except Exception as e:
            logger.error(f"Failed to fetch cameras: {e}")
            self._local.conn = None
        return cameras

    def update_camera_status(self, camera_id: str, status: str):
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE cameras SET status = %s, updated_at = NOW() WHERE id = %s",
                    (status, camera_id),
                )
        except Exception as e:
            logger.error(f"Failed to update camera status for {camera_id}: {e}")
            self._local.conn = None

    def insert_event(
        self,
        camera_id: str,
        event_type: str,
        label: str,
        confidence: float,
        bbox: dict,
        tracker_id: Optional[int],
        snapshot_url: str,
        detected_at: datetime,
    ) -> Optional[str]:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
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
                        camera_id,
                        event_type,
                        label,
                        confidence,
                        json.dumps(bbox),
                        tracker_id,
                        snapshot_url,
                        detected_at,
                    ),
                )
                result = cur.fetchone()
                return str(result[0]) if result else None
        except Exception as e:
            logger.error(f"Failed to insert event: {e}")
            self._local.conn = None
            return None


# ────────────────────────────────────────────────────────────
# MinIO helper
# ────────────────────────────────────────────────────────────

class SnapshotUploader:
    """Uploads JPEG snapshots to MinIO."""

    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_user,
            secret_key=settings.minio_password,
            secure=False,
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        bucket = settings.minio_bucket_snapshots
        try:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
                logger.info(f"Created MinIO bucket: {bucket}")
        except S3Error as e:
            logger.error(f"MinIO bucket check failed: {e}")

    def upload(self, frame: np.ndarray, camera_id: str, detection: Detection) -> str:
        """
        Encode frame region as JPEG and upload to MinIO.
        Returns the object path (used as snapshot_url).
        """
        bucket = settings.minio_bucket_snapshots
        now = datetime.now(timezone.utc)
        date_prefix = now.strftime("%Y/%m/%d")
        filename = f"{camera_id}/{date_prefix}/{now.strftime('%H%M%S')}_{detection.label}_{uuid.uuid4().hex[:8]}.jpg"

        try:
            # Encode full frame as JPEG (not just the crop — more context)
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            data = io.BytesIO(buf.tobytes())
            size = data.getbuffer().nbytes

            self.client.put_object(
                bucket,
                filename,
                data,
                length=size,
                content_type="image/jpeg",
            )
            return f"{bucket}/{filename}"
        except Exception as e:
            logger.error(f"Snapshot upload failed: {e}")
            return ""


# ────────────────────────────────────────────────────────────
# Camera processing thread
# ────────────────────────────────────────────────────────────

class CameraProcessor:
    """Processes a single RTSP camera in its own thread."""

    def __init__(
        self,
        camera_id: str,
        camera_name: str,
        rtsp_url: str,
        detector: YOLODetector,
        db: DatabaseManager,
        redis_client: redis.Redis,
        uploader: SnapshotUploader,
    ):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.rtsp_url = rtsp_url
        self.detector = detector
        self.db = db
        self.redis_client = redis_client
        self.uploader = uploader

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._frame_count = 0
        self._detection_count = 0
        self._event_count = 0

        # Deduplication: {dedup_key: last_event_timestamp}
        # dedup_key = tracker_id if available, else "label:grid_cell"
        self._recent_trackers: dict[str, float] = {}

    @property
    def stats(self) -> dict:
        return {
            "camera_id": self.camera_id,
            "name": self.camera_name,
            "frames": self._frame_count,
            "detections": self._detection_count,
            "events": self._event_count,
        }

    def start(self):
        self._thread = threading.Thread(
            target=self._run,
            name=f"cam-{self.camera_name}",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

    def _run(self):
        """Main capture-detect loop with reconnection logic."""
        while not self._stop_event.is_set():
            cap = None
            try:
                logger.info(f"[{self.camera_name}] Connecting to RTSP: {self.rtsp_url}")
                cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)

                # Tune RTSP capture for low latency
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                if not cap.isOpened():
                    raise ConnectionError("Failed to open RTSP stream")

                logger.info(f"[{self.camera_name}] Connected — starting detection loop")
                self.db.update_camera_status(self.camera_id, "online")

                consecutive_failures = 0
                while not self._stop_event.is_set():
                    ret, frame = cap.read()
                    if not ret:
                        consecutive_failures += 1
                        if consecutive_failures > 30:
                            raise ConnectionError(
                                f"Lost RTSP stream after {consecutive_failures} failed reads"
                            )
                        time.sleep(0.05)
                        continue

                    consecutive_failures = 0
                    self._frame_count += 1

                    # Only process every Nth frame
                    if self._frame_count % settings.process_every_n_frames != 0:
                        continue

                    # Run YOLO detection + tracking
                    detections = self.detector.detect(frame, use_tracker=True)
                    if not detections:
                        continue

                    self._detection_count += len(detections)
                    now = time.time()

                    for det in detections:
                        # Publish every detection to Redis (real-time feed)
                        self._publish_detection(det, now)

                        # Build dedup key: prefer tracker_id, fallback to label+grid
                        if det.tracker_id is not None:
                            dedup_key = f"t:{det.tracker_id}"
                        else:
                            # Grid-based dedup: divide frame into 8x8 cells
                            cx = (det.bbox["x1"] + det.bbox["x2"]) / 2
                            cy = (det.bbox["y1"] + det.bbox["y2"]) / 2
                            gx = int(cx / 200)  # ~200px grid cells
                            gy = int(cy / 200)
                            dedup_key = f"g:{det.label}:{gx}:{gy}"

                        last_seen = self._recent_trackers.get(dedup_key)
                        if last_seen and (now - last_seen) < settings.dedup_window_seconds:
                            continue
                        self._recent_trackers[dedup_key] = now

                        # Upload snapshot
                        snapshot_url = self.uploader.upload(frame, self.camera_id, det)

                        # Save event to DB
                        detected_at = datetime.now(timezone.utc)
                        event_id = self.db.insert_event(
                            camera_id=self.camera_id,
                            event_type=det.event_type,
                            label=det.label,
                            confidence=det.confidence,
                            bbox=det.bbox,
                            tracker_id=det.tracker_id,
                            snapshot_url=snapshot_url,
                            detected_at=detected_at,
                        )

                        if event_id:
                            self._event_count += 1
                            logger.info(
                                f"[{self.camera_name}] Event: {det.event_type} "
                                f"label={det.label} conf={det.confidence:.2f} "
                                f"tracker={det.tracker_id} id={event_id}"
                            )

                    # Periodically clean old dedup entries
                    if self._frame_count % 300 == 0:
                        self._clean_dedup(now)

            except Exception as e:
                logger.error(f"[{self.camera_name}] Error: {e}")
                self.db.update_camera_status(self.camera_id, "offline")
            finally:
                if cap is not None:
                    cap.release()

            # Wait before reconnecting
            if not self._stop_event.is_set():
                logger.info(
                    f"[{self.camera_name}] Reconnecting in {settings.reconnect_interval}s..."
                )
                self._stop_event.wait(timeout=settings.reconnect_interval)

    def _publish_detection(self, det: Detection, timestamp: float):
        """Publish detection to Redis pub/sub channels."""
        payload = json.dumps({
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "label": det.label,
            "event_type": det.event_type,
            "confidence": det.confidence,
            "bbox": det.bbox,
            "tracker_id": det.tracker_id,
            "timestamp": timestamp,
        })
        try:
            self.redis_client.publish(f"detections:{self.camera_id}", payload)
            self.redis_client.publish("detections:all", payload)
        except Exception as e:
            logger.warning(f"Redis publish failed: {e}")

    def _clean_dedup(self, now: float):
        """Remove expired tracker entries from dedup cache."""
        cutoff = now - settings.dedup_window_seconds * 2
        self._recent_trackers = {
            tid: ts for tid, ts in self._recent_trackers.items() if ts > cutoff
        }


# ────────────────────────────────────────────────────────────
# Main service
# ────────────────────────────────────────────────────────────

class DetectorService:
    """Orchestrates camera threads, YOLO model, and stats logging."""

    def __init__(self):
        self._running = False
        self._processors: list[CameraProcessor] = []
        self._lock = threading.Lock()

    def start(self):
        logger.info("=" * 60)
        logger.info("Deep Vision by DNS — YOLO Detector Starting")
        logger.info(f"Model: {settings.yolo_model}")
        logger.info(f"Confidence threshold: {settings.confidence_threshold}")
        logger.info(f"Process every {settings.process_every_n_frames} frames")
        logger.info(f"Dedup window: {settings.dedup_window_seconds}s")
        logger.info("=" * 60)

        # Initialize shared components
        detector = YOLODetector()
        db = DatabaseManager()
        uploader = SnapshotUploader()

        redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )
        try:
            redis_client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")

        # Load cameras from database
        cameras = db.fetch_cameras()
        if not cameras:
            logger.warning("No enabled cameras found in database")

        logger.info(f"Loaded {len(cameras)} cameras")

        # Spawn a processing thread per camera
        self._running = True
        for cam_id, cam_data in cameras.items():
            processor = CameraProcessor(
                camera_id=cam_id,
                camera_name=cam_data["name"],
                rtsp_url=cam_data["rtsp_url"],
                detector=detector,
                db=db,
                redis_client=redis_client,
                uploader=uploader,
            )
            self._processors.append(processor)
            processor.start()
            logger.info(f"Started processor for camera: {cam_data['name']} ({cam_id})")

        # Stats logging loop (runs on main thread)
        self._stats_loop()

    def _stats_loop(self):
        """Periodically log detection stats for all cameras."""
        while self._running:
            time.sleep(settings.stats_interval_seconds)
            if not self._running:
                break
            total_detections = 0
            total_events = 0
            for proc in self._processors:
                s = proc.stats
                total_detections += s["detections"]
                total_events += s["events"]
                logger.info(
                    f"Stats [{s['name']}] frames={s['frames']} "
                    f"detections={s['detections']} events={s['events']}"
                )
            logger.info(
                f"Stats [TOTAL] cameras={len(self._processors)} "
                f"detections={total_detections} events={total_events}"
            )

    def stop(self):
        logger.info("Detector shutting down...")
        self._running = False
        for proc in self._processors:
            proc.stop()
        logger.info("All camera processors stopped")
        logger.info("Detector stopped")


def main():
    service = DetectorService()

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        service.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    service.start()


if __name__ == "__main__":
    main()
