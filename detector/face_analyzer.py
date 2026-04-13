"""
Face Analyzer — DeepFace-powered face detection and recognition.

When a person is detected by YOLO, this module:
1. Crops the person bbox from the frame
2. Runs face detection + embedding extraction via DeepFace
3. Compares the embedding against the known_persons database
4. Returns match results (person_id, confidence, face attributes)

Uses RetinaFace for detection (best accuracy) and ArcFace for recognition
(best embedding model). Both run on GPU if CUDA is available.
"""

import io
import logging
import threading
import time
import pickle
from typing import Optional
from dataclasses import dataclass

import cv2
import numpy as np
import psycopg2
import psycopg2.extras

from config import settings

logger = logging.getLogger(__name__)

# Lazy import — DeepFace is heavy
_deepface = None
_deepface_lock = threading.Lock()


def _get_deepface():
    """Lazy-load DeepFace to avoid slow startup."""
    global _deepface
    if _deepface is None:
        with _deepface_lock:
            if _deepface is None:
                try:
                    from deepface import DeepFace
                    _deepface = DeepFace
                    logger.info("DeepFace loaded successfully")
                except ImportError:
                    logger.error("DeepFace not installed — face recognition disabled")
    return _deepface


@dataclass
class FaceResult:
    """Result of face analysis on a detection."""
    face_detected: bool = False
    face_confidence: float = 0.0
    face_bbox: Optional[dict] = None  # relative to the crop
    person_id: Optional[str] = None
    person_name: Optional[str] = None
    match_distance: Optional[float] = None
    match_threshold: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    emotion: Optional[str] = None
    embedding: Optional[list] = None


class FaceAnalyzer:
    """
    Analyzes faces in person detections using DeepFace.

    Workflow:
    1. Crop person bbox from frame
    2. Detect face in crop (RetinaFace)
    3. Extract embedding (ArcFace)
    4. Compare against known_persons database
    5. Optionally analyze age, gender, emotion
    """

    def __init__(self):
        self.enabled = settings.face_recognition_enabled
        self.detector_backend = settings.face_detector_backend
        self.recognition_model = settings.face_recognition_model
        self.match_threshold = settings.face_match_threshold
        self.min_face_size = settings.face_min_size
        self.analyze_attributes = settings.face_analyze_attributes

        # Known persons cache: list of (person_id, name, embedding_vector)
        self._known_persons: list[tuple[str, str, np.ndarray]] = []
        self._known_persons_lock = threading.Lock()
        self._last_db_refresh = 0.0
        self._db_refresh_interval = 300.0  # Refresh every 5 minutes

        # Stats
        self._stats = {
            "faces_analyzed": 0,
            "faces_detected": 0,
            "faces_matched": 0,
            "faces_unknown": 0,
        }

        if self.enabled:
            # Pre-load DeepFace in background
            threading.Thread(target=self._warmup, daemon=True).start()

        logger.info(
            f"FaceAnalyzer initialized: enabled={self.enabled}, "
            f"detector={self.detector_backend}, model={self.recognition_model}, "
            f"threshold={self.match_threshold}"
        )

    def _warmup(self):
        """Pre-load DeepFace models in background thread."""
        try:
            DeepFace = _get_deepface()
            if DeepFace is None:
                return

            # Build models on first call (downloads if needed)
            logger.info("Warming up DeepFace models...")
            # Create a small dummy image to trigger model loading
            dummy = np.zeros((160, 160, 3), dtype=np.uint8)
            dummy[40:120, 40:120] = 200  # light area to simulate face

            try:
                DeepFace.represent(
                    dummy,
                    model_name=self.recognition_model,
                    detector_backend=self.detector_backend,
                    enforce_detection=False,
                )
            except Exception:
                pass  # Expected to fail on dummy image, but models are loaded

            logger.info("DeepFace models warmed up")

            # Load known persons from DB
            self._refresh_known_persons()

        except Exception as e:
            logger.error(f"DeepFace warmup failed: {e}")

    def _refresh_known_persons(self):
        """Load known persons and their embeddings from PostgreSQL."""
        now = time.time()
        if now - self._last_db_refresh < self._db_refresh_interval:
            return

        try:
            conn = psycopg2.connect(settings.db_url)
            conn.autocommit = True
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, name, face_encoding FROM known_persons "
                    "WHERE is_active = true AND face_encoding IS NOT NULL"
                )
                rows = cur.fetchall()

            persons = []
            for row in rows:
                try:
                    embedding = pickle.loads(row["face_encoding"])
                    if isinstance(embedding, np.ndarray):
                        persons.append((str(row["id"]), row["name"], embedding))
                except Exception as e:
                    logger.warning(f"Failed to decode embedding for {row['name']}: {e}")

            with self._known_persons_lock:
                self._known_persons = persons

            self._last_db_refresh = now
            logger.info(f"FaceAnalyzer: loaded {len(persons)} known persons from DB")
            conn.close()

        except Exception as e:
            logger.error(f"Failed to refresh known persons: {e}")

    def analyze(self, frame: np.ndarray, bbox: dict) -> FaceResult:
        """
        Analyze a person detection for face recognition.

        Args:
            frame: Full BGR frame from camera
            bbox: Detection bounding box {x1, y1, x2, y2}

        Returns:
            FaceResult with detection/recognition results
        """
        if not self.enabled:
            return FaceResult()

        DeepFace = _get_deepface()
        if DeepFace is None:
            return FaceResult()

        self._stats["faces_analyzed"] += 1

        # Periodically refresh known persons
        self._refresh_known_persons()

        # Crop person from frame with padding
        result = FaceResult()
        try:
            h, w = frame.shape[:2]
            x1 = max(0, int(bbox["x1"]))
            y1 = max(0, int(bbox["y1"]))
            x2 = min(w, int(bbox["x2"]))
            y2 = min(h, int(bbox["y2"]))

            # Add padding around crop (20% each side)
            pad_w = int((x2 - x1) * 0.1)
            pad_h = int((y2 - y1) * 0.1)
            x1 = max(0, x1 - pad_w)
            y1 = max(0, y1 - pad_h)
            x2 = min(w, x2 + pad_w)
            y2 = min(h, y2 + pad_h)

            crop = frame[y1:y2, x1:x2]
            if crop.size == 0 or crop.shape[0] < self.min_face_size or crop.shape[1] < self.min_face_size:
                return result

            # Detect face and extract embedding
            try:
                representations = DeepFace.represent(
                    crop,
                    model_name=self.recognition_model,
                    detector_backend=self.detector_backend,
                    enforce_detection=False,
                    align=True,
                )
            except Exception as e:
                logger.debug(f"DeepFace.represent failed: {e}")
                return result

            if not representations or len(representations) == 0:
                return result

            # Take the first (largest) face
            face_data = representations[0]
            embedding = np.array(face_data["embedding"])

            # Check if face was actually detected (not just the full image)
            face_area = face_data.get("facial_area", {})
            face_confidence = face_data.get("face_confidence", 0.0)

            if face_confidence < 0.5:
                return result

            result.face_detected = True
            result.face_confidence = round(float(face_confidence), 3)
            result.embedding = embedding.tolist()
            self._stats["faces_detected"] += 1

            if face_area:
                result.face_bbox = {
                    "x": face_area.get("x", 0),
                    "y": face_area.get("y", 0),
                    "w": face_area.get("w", 0),
                    "h": face_area.get("h", 0),
                }

            # Match against known persons
            match = self._find_match(embedding)
            if match:
                result.person_id = match[0]
                result.person_name = match[1]
                result.match_distance = match[2]
                result.match_threshold = self.match_threshold
                self._stats["faces_matched"] += 1
                logger.info(
                    f"Face matched: {match[1]} (distance={match[2]:.4f}, "
                    f"threshold={self.match_threshold})"
                )
            else:
                self._stats["faces_unknown"] += 1

            # Optionally analyze age, gender, emotion
            if self.analyze_attributes:
                try:
                    analysis = DeepFace.analyze(
                        crop,
                        actions=["age", "gender", "emotion"],
                        detector_backend=self.detector_backend,
                        enforce_detection=False,
                        silent=True,
                    )
                    if analysis and len(analysis) > 0:
                        a = analysis[0]
                        result.age = a.get("age")
                        result.gender = a.get("dominant_gender")
                        result.emotion = a.get("dominant_emotion")
                except Exception:
                    pass  # Attribute analysis is optional

        except Exception as e:
            logger.error(f"Face analysis error: {e}")

        return result

    def _find_match(self, embedding: np.ndarray) -> Optional[tuple[str, str, float]]:
        """
        Find the closest matching known person.

        Returns (person_id, name, distance) if match found, None otherwise.
        Uses cosine distance for ArcFace embeddings.
        """
        with self._known_persons_lock:
            if not self._known_persons:
                return None

        best_match = None
        best_distance = float("inf")

        with self._known_persons_lock:
            for person_id, name, known_embedding in self._known_persons:
                # Cosine distance
                dot = np.dot(embedding, known_embedding)
                norm_a = np.linalg.norm(embedding)
                norm_b = np.linalg.norm(known_embedding)
                if norm_a == 0 or norm_b == 0:
                    continue
                cosine_sim = dot / (norm_a * norm_b)
                distance = 1.0 - cosine_sim

                if distance < best_distance:
                    best_distance = distance
                    best_match = (person_id, name, round(distance, 4))

        if best_match and best_distance <= self.match_threshold:
            return best_match

        return None

    def register_face(self, name: str, photo: np.ndarray,
                      employee_id: str = None, department: str = None,
                      photo_url: str = "") -> Optional[dict]:
        """
        Register a new person in the face database.

        Args:
            name: Person's name
            photo: BGR image containing the person's face
            employee_id: Optional employee ID
            department: Optional department
            photo_url: URL of the uploaded photo

        Returns:
            Dict with person_id and embedding info, or None if failed
        """
        DeepFace = _get_deepface()
        if DeepFace is None:
            return None

        try:
            # Extract face embedding
            representations = DeepFace.represent(
                photo,
                model_name=self.recognition_model,
                detector_backend=self.detector_backend,
                enforce_detection=True,
                align=True,
            )

            if not representations:
                logger.error("No face detected in registration photo")
                return None

            embedding = np.array(representations[0]["embedding"])
            face_confidence = representations[0].get("face_confidence", 0.0)

            # Serialize embedding
            encoding_bytes = pickle.dumps(embedding)

            # Store in database
            conn = psycopg2.connect(settings.db_url)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO known_persons (name, employee_id, department,
                       face_encoding, photo_url, is_active)
                    VALUES (%s, %s, %s, %s, %s, true) RETURNING id""",
                    (name, employee_id, department, encoding_bytes, photo_url),
                )
                person_id = str(cur.fetchone()[0])
            conn.close()

            # Refresh cache
            self._last_db_refresh = 0  # Force refresh
            self._refresh_known_persons()

            logger.info(f"Registered new person: {name} (id={person_id})")
            return {
                "person_id": person_id,
                "name": name,
                "face_confidence": float(face_confidence),
                "embedding_size": len(embedding),
            }

        except Exception as e:
            logger.error(f"Face registration failed: {e}")
            return None

    def get_stats(self) -> dict:
        """Return face analysis statistics."""
        with self._known_persons_lock:
            known_count = len(self._known_persons)
        return {
            **self._stats,
            "known_persons": known_count,
        }
