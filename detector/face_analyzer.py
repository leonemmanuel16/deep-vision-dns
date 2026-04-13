"""
Face Analyzer — HTTP client for the face-analyzer microservice.

Sends person crops to the face-analyzer service via HTTP POST.
The face-analyzer runs TensorFlow/DeepFace in its own container,
avoiding CUDA conflicts with PyTorch/YOLO in this process.
"""

import io
import logging
import threading
import time
from typing import Optional
from dataclasses import dataclass

import cv2
import numpy as np
import requests

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class FaceResult:
    """Result of face analysis on a detection."""
    face_detected: bool = False
    face_confidence: float = 0.0
    face_bbox: Optional[dict] = None
    person_id: Optional[str] = None
    person_name: Optional[str] = None
    is_unknown: bool = False
    match_distance: Optional[float] = None
    match_threshold: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    emotion: Optional[str] = None
    embedding: Optional[list] = None


class FaceAnalyzer:
    """
    HTTP client that sends person crops to the face-analyzer microservice.
    All face detection, recognition, and registration happens in the
    separate face-analyzer container (TensorFlow/DeepFace on CPU).
    """

    def __init__(self, snapshot_uploader=None):
        self.enabled = settings.face_recognition_enabled
        self.snapshot_uploader = snapshot_uploader
        self._service_url = getattr(settings, 'face_analyzer_url', 'http://face-analyzer:8002')
        self._service_available = False
        self._last_health_check = 0.0
        self._health_check_interval = 30.0

        # Stats
        self._stats = {
            "faces_analyzed": 0,
            "faces_detected": 0,
            "faces_matched": 0,
            "faces_unknown": 0,
            "unknowns_registered": 0,
        }
        self._lock = threading.Lock()

        if self.enabled:
            threading.Thread(target=self._check_service, daemon=True).start()

        logger.info(
            f"FaceAnalyzer initialized: enabled={self.enabled}, "
            f"service_url={self._service_url}, mode=microservice"
        )

    def _check_service(self):
        """Check if face-analyzer service is available."""
        # Wait for service to start
        time.sleep(10)
        for attempt in range(10):
            try:
                resp = requests.get(f"{self._service_url}/health", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    self._service_available = True
                    logger.info(
                        f"Face-analyzer service connected: "
                        f"model={data.get('model')}, detector={data.get('detector')}"
                    )
                    return
            except Exception:
                pass
            logger.info(f"Waiting for face-analyzer service... (attempt {attempt + 1}/10)")
            time.sleep(10)

        logger.warning("Face-analyzer service not available — face recognition disabled")
        self.enabled = False

    def _is_service_ready(self) -> bool:
        """Check if service is available (with periodic health checks)."""
        if self._service_available:
            now = time.time()
            if now - self._last_health_check > self._health_check_interval:
                try:
                    resp = requests.get(f"{self._service_url}/health", timeout=3)
                    self._service_available = resp.status_code == 200
                    self._last_health_check = now
                except Exception:
                    self._service_available = False
            return self._service_available
        return False

    def analyze(self, frame: np.ndarray, bbox: dict,
                camera_id: str = None) -> FaceResult:
        """
        Send person crop to face-analyzer microservice for analysis.

        Args:
            frame: Full BGR frame from camera
            bbox: Detection bounding box {x1, y1, x2, y2}
            camera_id: Camera ID for unknown registration

        Returns:
            FaceResult with detection/recognition results
        """
        if not self.enabled or not self._is_service_ready():
            return FaceResult()

        with self._lock:
            self._stats["faces_analyzed"] += 1

        result = FaceResult()
        try:
            # Encode frame as JPEG
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            image_bytes = buf.tobytes()

            # Send to face-analyzer service
            files = {"image": ("frame.jpg", io.BytesIO(image_bytes), "image/jpeg")}
            data = {
                "bbox_x1": bbox.get("x1", 0),
                "bbox_y1": bbox.get("y1", 0),
                "bbox_x2": bbox.get("x2", 0),
                "bbox_y2": bbox.get("y2", 0),
                "camera_id": camera_id or "",
            }

            resp = requests.post(
                f"{self._service_url}/analyze",
                files=files,
                data=data,
                timeout=10,
            )

            if resp.status_code != 200:
                return result

            r = resp.json()

            if not r.get("face_detected"):
                return result

            result.face_detected = True
            result.face_confidence = r.get("face_confidence", 0.0)
            result.face_bbox = r.get("face_bbox")
            result.person_id = r.get("person_id")
            result.person_name = r.get("person_name")
            result.is_unknown = r.get("is_unknown", False)
            result.match_distance = r.get("match_distance")
            result.match_threshold = settings.face_match_threshold
            result.age = r.get("age")
            result.gender = r.get("gender")
            result.emotion = r.get("emotion")

            with self._lock:
                self._stats["faces_detected"] += 1
                if result.person_id:
                    if result.is_unknown:
                        self._stats["faces_unknown"] += 1
                    else:
                        self._stats["faces_matched"] += 1

            if result.person_name and not result.is_unknown:
                logger.info(
                    f"Face matched: {result.person_name} "
                    f"(distance={result.match_distance})"
                )

        except requests.exceptions.Timeout:
            logger.debug("Face-analyzer request timed out")
        except requests.exceptions.ConnectionError:
            self._service_available = False
            logger.debug("Face-analyzer service unreachable")
        except Exception as e:
            logger.error(f"Face analysis error: {e}")

        return result

    def get_stats(self) -> dict:
        """Return face analysis statistics."""
        with self._lock:
            stats = dict(self._stats)
        stats["service_available"] = self._service_available
        stats["service_url"] = self._service_url
        return stats
