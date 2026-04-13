"""
Face Analyzer — DeepFace-powered face detection and recognition.

When a person is detected by YOLO, this module:
1. Crops the person bbox from the frame
2. Runs face detection + embedding extraction via DeepFace
3. Compares the embedding against the known_persons database
4. If matched → returns person_id
5. If NOT matched → auto-registers as "Desconocido" with snapshot + embedding
6. Returns match results (person_id, confidence, face attributes)

Uses RetinaFace for detection (best accuracy) and ArcFace for recognition
(best embedding model). Both run on GPU if CUDA is available.
"""

import io
import logging
import threading
import time
import pickle
import uuid
from datetime import datetime, timezone
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
    """Lazy-load DeepFace to avoid slow startup.
    Forces TensorFlow to CPU to preserve GPU memory for YOLO."""
    global _deepface
    if _deepface is None:
        with _deepface_lock:
            if _deepface is None:
                try:
                    import os
                    # Suppress TF verbose logs
                    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

                    # Force TensorFlow to CPU — GPU memory reserved for YOLO
                    import tensorflow as tf
                    try:
                        tf.config.set_visible_devices([], 'GPU')
                        logger.info("TensorFlow forced to CPU mode (GPU reserved for YOLO)")
                    except RuntimeError:
                        # GPU devices already initialized — limit memory instead
                        for gpu in tf.config.list_physical_devices('GPU'):
                            tf.config.experimental.set_memory_growth(gpu, True)
                        logger.info("TensorFlow GPU memory growth enabled")

                    from deepface import DeepFace
                    _deepface = DeepFace
                    logger.info("DeepFace loaded successfully (CPU mode)")
                except ImportError:
                    logger.error("DeepFace not installed — face recognition disabled")
                except Exception as e:
                    logger.error(f"DeepFace init error: {e}")
    return _deepface


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
    Analyzes faces in person detections using DeepFace.

    Workflow:
    1. Crop person bbox from frame
    2. Detect face in crop (RetinaFace)
    3. Extract embedding (ArcFace)
    4. Compare against ALL persons in DB (known + unknown)
    5. If match found → return person_id
    6. If NO match → auto-register as "Desconocido" with snapshot
    7. Optionally analyze age, gender, emotion
    """

    def __init__(self, snapshot_uploader=None):
        self.enabled = settings.face_recognition_enabled
        self.detector_backend = settings.face_detector_backend
        self.recognition_model = settings.face_recognition_model
        self.match_threshold = settings.face_match_threshold
        self.min_face_size = settings.face_min_size
        self.analyze_attributes = settings.face_analyze_attributes
        self.snapshot_uploader = snapshot_uploader

        # Known persons cache: list of (person_id, name, embedding_vector, is_unknown)
        self._known_persons: list[tuple[str, str, np.ndarray, bool]] = []
        self._known_persons_lock = threading.Lock()
        self._last_db_refresh = 0.0
        self._db_refresh_interval = 120.0  # Refresh every 2 minutes

        # Dedup: recently registered unknowns (avoid re-registering same face)
        self._recent_unknown_ids: dict[str, float] = {}  # embedding_hash -> timestamp
        self._unknown_dedup_lock = threading.Lock()

        # Stats
        self._stats = {
            "faces_analyzed": 0,
            "faces_detected": 0,
            "faces_matched": 0,
            "faces_unknown": 0,
            "unknowns_registered": 0,
        }

        if self.enabled:
            threading.Thread(target=self._warmup, daemon=True).start()

        logger.info(
            f"FaceAnalyzer initialized: enabled={self.enabled}, "
            f"detector={self.detector_backend}, model={self.recognition_model}, "
            f"threshold={self.match_threshold}, auto_register_unknowns=True"
        )

    def _warmup(self):
        """Pre-load DeepFace models in background thread."""
        try:
            DeepFace = _get_deepface()
            if DeepFace is None:
                return

            logger.info("Warming up DeepFace models...")
            dummy = np.zeros((160, 160, 3), dtype=np.uint8)
            dummy[40:120, 40:120] = 200

            try:
                DeepFace.represent(
                    dummy,
                    model_name=self.recognition_model,
                    detector_backend=self.detector_backend,
                    enforce_detection=False,
                )
            except Exception:
                pass

            logger.info("DeepFace models warmed up")
            self._refresh_known_persons()

        except Exception as e:
            logger.error(f"DeepFace warmup failed: {e}")

    def _refresh_known_persons(self):
        """Load ALL persons (known + unknown) and their embeddings from PostgreSQL."""
        now = time.time()
        if now - self._last_db_refresh < self._db_refresh_interval:
            return

        try:
            conn = psycopg2.connect(settings.db_url)
            conn.autocommit = True
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, name, face_encoding, is_unknown FROM known_persons "
                    "WHERE is_active = true AND face_encoding IS NOT NULL "
                    "AND merged_into_id IS NULL"
                )
                rows = cur.fetchall()

            persons = []
            for row in rows:
                try:
                    embedding = pickle.loads(row["face_encoding"])
                    if isinstance(embedding, np.ndarray):
                        persons.append((
                            str(row["id"]),
                            row["name"],
                            embedding,
                            bool(row.get("is_unknown", False)),
                        ))
                except Exception as e:
                    logger.warning(f"Failed to decode embedding for {row['name']}: {e}")

            with self._known_persons_lock:
                self._known_persons = persons

            self._last_db_refresh = now
            known_count = sum(1 for p in persons if not p[3])
            unknown_count = sum(1 for p in persons if p[3])
            logger.info(
                f"FaceAnalyzer: loaded {len(persons)} persons "
                f"({known_count} known, {unknown_count} unknown)"
            )
            conn.close()

        except Exception as e:
            logger.error(f"Failed to refresh known persons: {e}")

    def analyze(self, frame: np.ndarray, bbox: dict,
                camera_id: str = None) -> FaceResult:
        """
        Analyze a person detection for face recognition.
        If face is detected but not matched, auto-registers as "Desconocido".

        Args:
            frame: Full BGR frame from camera
            bbox: Detection bounding box {x1, y1, x2, y2}
            camera_id: Camera ID for unknown registration

        Returns:
            FaceResult with detection/recognition results
        """
        if not self.enabled:
            return FaceResult()

        DeepFace = _get_deepface()
        if DeepFace is None:
            return FaceResult()

        self._stats["faces_analyzed"] += 1
        self._refresh_known_persons()

        result = FaceResult()
        try:
            h, w = frame.shape[:2]
            x1 = max(0, int(bbox["x1"]))
            y1 = max(0, int(bbox["y1"]))
            x2 = min(w, int(bbox["x2"]))
            y2 = min(h, int(bbox["y2"]))

            # Add padding
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

            face_data = representations[0]
            embedding = np.array(face_data["embedding"])
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

            # Match against ALL persons (known + unknown)
            match = self._find_match(embedding)
            if match:
                result.person_id = match[0]
                result.person_name = match[1]
                result.match_distance = match[2]
                result.match_threshold = self.match_threshold
                result.is_unknown = match[3]  # True if matched to an unknown

                if match[3]:
                    # Matched to existing unknown — update times_seen
                    self._update_unknown_seen(match[0])
                    self._stats["faces_unknown"] += 1
                    logger.debug(
                        f"Face matched existing unknown: {match[0][:8]} "
                        f"(distance={match[2]:.4f})"
                    )
                else:
                    self._stats["faces_matched"] += 1
                    logger.info(
                        f"Face matched: {match[1]} (distance={match[2]:.4f})"
                    )
            else:
                # ── NEW: Auto-register as "Desconocido" ──
                self._stats["faces_unknown"] += 1
                unknown_id = self._register_unknown(
                    embedding, crop, frame, bbox, camera_id
                )
                if unknown_id:
                    result.person_id = unknown_id
                    result.person_name = "Desconocido"
                    result.is_unknown = True

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
                    pass

        except Exception as e:
            logger.error(f"Face analysis error: {e}")

        return result

    def _find_match(self, embedding: np.ndarray) -> Optional[tuple[str, str, float, bool]]:
        """
        Find the closest matching person (known or unknown).

        Returns (person_id, name, distance, is_unknown) if match found.
        Searches both known persons AND previously registered unknowns.
        """
        with self._known_persons_lock:
            if not self._known_persons:
                return None

        best_match = None
        best_distance = float("inf")

        with self._known_persons_lock:
            for person_id, name, known_embedding, is_unknown in self._known_persons:
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
                    best_match = (person_id, name, round(distance, 4), is_unknown)

        if best_match and best_distance <= self.match_threshold:
            return best_match

        return None

    def _register_unknown(self, embedding: np.ndarray, face_crop: np.ndarray,
                          full_frame: np.ndarray, bbox: dict,
                          camera_id: str = None) -> Optional[str]:
        """
        Auto-register an unmatched face as "Desconocido" in the database.

        Saves the face embedding + a cropped snapshot for later identification.
        Uses dedup to avoid registering the same face multiple times in quick succession.
        """
        # Dedup: check if we recently registered a very similar face
        emb_hash = self._embedding_hash(embedding)
        now = time.time()
        with self._unknown_dedup_lock:
            last_registered = self._recent_unknown_ids.get(emb_hash)
            if last_registered and (now - last_registered) < 120:  # 2 min cooldown
                return None
            self._recent_unknown_ids[emb_hash] = now

            # Clean old entries
            if len(self._recent_unknown_ids) > 500:
                cutoff = now - 300
                self._recent_unknown_ids = {
                    k: v for k, v in self._recent_unknown_ids.items() if v > cutoff
                }

        try:
            encoding_bytes = pickle.dumps(embedding)

            # Upload face crop as photo
            photo_url = ""
            if self.snapshot_uploader is not None:
                try:
                    photo_url = self.snapshot_uploader.upload(
                        face_crop, camera_id or "unknown", "desconocido"
                    )
                except Exception:
                    pass

            # Count existing unknowns for naming
            conn = psycopg2.connect(settings.db_url)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM known_persons WHERE is_unknown = true")
                unknown_count = cur.fetchone()[0] + 1

                detected_at = datetime.now(timezone.utc)
                name = f"Desconocido #{unknown_count}"

                cur.execute(
                    """INSERT INTO known_persons
                       (name, face_encoding, photo_url, is_active, is_unknown,
                        first_seen_camera_id, first_seen_at, times_seen, last_seen_at,
                        notes)
                    VALUES (%s, %s, %s, true, true, %s, %s, 1, %s, %s)
                    RETURNING id""",
                    (
                        name, encoding_bytes, photo_url,
                        camera_id, detected_at, detected_at,
                        f"Detectado automáticamente por cámara",
                    ),
                )
                person_id = str(cur.fetchone()[0])
            conn.close()

            # Add to in-memory cache immediately
            with self._known_persons_lock:
                self._known_persons.append((person_id, name, embedding, True))

            self._stats["unknowns_registered"] += 1
            logger.info(
                f"Auto-registered unknown face: {name} (id={person_id[:8]}, "
                f"camera={camera_id})"
            )
            return person_id

        except Exception as e:
            logger.error(f"Failed to register unknown face: {e}")
            return None

    def _update_unknown_seen(self, person_id: str):
        """Update times_seen and last_seen_at for an unknown person."""
        try:
            conn = psycopg2.connect(settings.db_url)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE known_persons
                    SET times_seen = times_seen + 1,
                        last_seen_at = NOW()
                    WHERE id = %s""",
                    (person_id,),
                )
            conn.close()
        except Exception:
            pass  # Non-critical

    @staticmethod
    def _embedding_hash(embedding: np.ndarray) -> str:
        """Create a rough hash of an embedding for dedup.
        Quantizes to 8 bins and creates a short hash string."""
        quantized = np.round(embedding[:32] * 10).astype(int)
        return hash(quantized.tobytes())

    def register_face(self, name: str, photo: np.ndarray,
                      employee_id: str = None, department: str = None,
                      photo_url: str = "") -> Optional[dict]:
        """Register a new known person in the face database."""
        DeepFace = _get_deepface()
        if DeepFace is None:
            return None

        try:
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
            encoding_bytes = pickle.dumps(embedding)

            conn = psycopg2.connect(settings.db_url)
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO known_persons (name, employee_id, department,
                       face_encoding, photo_url, is_active, is_unknown)
                    VALUES (%s, %s, %s, %s, %s, true, false) RETURNING id""",
                    (name, employee_id, department, encoding_bytes, photo_url),
                )
                person_id = str(cur.fetchone()[0])
            conn.close()

            self._last_db_refresh = 0
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
            known_count = sum(1 for p in self._known_persons if not p[3])
            unknown_count = sum(1 for p in self._known_persons if p[3])
        return {
            **self._stats,
            "known_persons": known_count,
            "unknown_persons": unknown_count,
        }
