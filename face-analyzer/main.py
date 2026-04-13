"""
Face Analyzer Microservice — Deep Vision by DNS

Separate process for DeepFace face recognition to avoid TF/PyTorch CUDA conflicts.
Runs TensorFlow on CPU, receives person crops via HTTP, returns face analysis results.

Endpoints:
  POST /analyze       — Analyze a person crop for face detection/recognition
  POST /register      — Register a new known person with photo
  GET  /persons       — List known persons
  GET  /health        — Health check
  GET  /stats         — Face analysis statistics
"""

import io
import logging
import pickle
import time
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager

import cv2
import numpy as np
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from minio import Minio
from minio.error import S3Error

from config import settings

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","msg":"%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("face-analyzer")

# ── DeepFace (TF on CPU) ────────────────────────────────────
_deepface = None


def _load_deepface():
    """Load DeepFace with TensorFlow in CPU-only mode."""
    global _deepface
    try:
        import tensorflow as tf
        tf.config.set_visible_devices([], 'GPU')
        logger.info("TensorFlow configured for CPU-only mode")
    except Exception as e:
        logger.warning(f"Could not configure TF GPU: {e}")

    from deepface import DeepFace
    _deepface = DeepFace
    logger.info("DeepFace loaded successfully")

    # Warmup
    logger.info("Warming up DeepFace models...")
    dummy = np.zeros((160, 160, 3), dtype=np.uint8)
    dummy[40:120, 40:120] = 200
    try:
        _deepface.represent(
            dummy,
            model_name=settings.face_recognition_model,
            detector_backend=settings.face_detector_backend,
            enforce_detection=False,
        )
    except Exception:
        pass
    logger.info("DeepFace models warmed up and ready")


# ── Known Persons Cache ─────────────────────────────────────
_known_persons: list[tuple[str, str, np.ndarray, bool]] = []
_known_persons_lock = threading.Lock()
_last_db_refresh = 0.0
_DB_REFRESH_INTERVAL = 120.0

# Stats
_stats = {
    "faces_analyzed": 0,
    "faces_detected": 0,
    "faces_matched": 0,
    "faces_unknown": 0,
    "unknowns_registered": 0,
}

# Dedup for unknown registration
_recent_unknown_hashes: dict[int, float] = {}
_unknown_dedup_lock = threading.Lock()


def _get_db_conn():
    conn = psycopg2.connect(settings.db_url)
    conn.autocommit = True
    return conn


def _refresh_known_persons():
    """Load all persons and their embeddings from PostgreSQL."""
    global _known_persons, _last_db_refresh
    now = time.time()
    if now - _last_db_refresh < _DB_REFRESH_INTERVAL:
        return

    try:
        conn = _get_db_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, face_encoding, is_unknown FROM known_persons "
                "WHERE is_active = true AND face_encoding IS NOT NULL "
                "AND merged_into_id IS NULL"
            )
            rows = cur.fetchall()
        conn.close()

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

        with _known_persons_lock:
            _known_persons = persons

        _last_db_refresh = now
        known_count = sum(1 for p in persons if not p[3])
        unknown_count = sum(1 for p in persons if p[3])
        logger.info(
            f"Loaded {len(persons)} persons ({known_count} known, {unknown_count} unknown)"
        )

    except Exception as e:
        logger.error(f"Failed to refresh known persons: {e}")


def _find_match(embedding: np.ndarray) -> Optional[tuple[str, str, float, bool]]:
    """Find closest matching person using cosine distance."""
    with _known_persons_lock:
        if not _known_persons:
            return None

    best_match = None
    best_distance = float("inf")

    with _known_persons_lock:
        for person_id, name, known_embedding, is_unknown in _known_persons:
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

    if best_match and best_distance <= settings.face_match_threshold:
        return best_match

    return None


def _embedding_hash(embedding: np.ndarray) -> int:
    """Create a rough hash of an embedding for dedup."""
    quantized = np.round(embedding[:32] * 10).astype(int)
    return hash(quantized.tobytes())


def _register_unknown(embedding: np.ndarray, face_crop: np.ndarray,
                       camera_id: str = None) -> Optional[str]:
    """Auto-register an unmatched face as Desconocido."""
    emb_hash = _embedding_hash(embedding)
    now = time.time()
    with _unknown_dedup_lock:
        last_registered = _recent_unknown_hashes.get(emb_hash)
        if last_registered and (now - last_registered) < 120:
            return None
        _recent_unknown_hashes[emb_hash] = now

        if len(_recent_unknown_hashes) > 500:
            cutoff = now - 300
            _recent_unknown_hashes.clear()

    try:
        encoding_bytes = pickle.dumps(embedding)

        # Upload face crop
        photo_url = ""
        try:
            minio_client = Minio(
                settings.minio_endpoint,
                access_key=settings.minio_user,
                secret_key=settings.minio_password,
                secure=False,
            )
            bucket = settings.minio_bucket_snapshots
            if not minio_client.bucket_exists(bucket):
                minio_client.make_bucket(bucket)

            now_dt = datetime.now(timezone.utc)
            filename = (
                f"faces/{camera_id or 'unknown'}/"
                f"{now_dt.strftime('%Y/%m/%d/%H%M%S')}_desconocido_{uuid.uuid4().hex[:8]}.jpg"
            )
            _, buf = cv2.imencode(".jpg", face_crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
            data = io.BytesIO(buf.tobytes())
            size = data.getbuffer().nbytes
            minio_client.put_object(bucket, filename, data, length=size,
                                     content_type="image/jpeg")
            photo_url = f"{bucket}/{filename}"
        except Exception as e:
            logger.warning(f"Failed to upload face crop: {e}")

        conn = _get_db_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM known_persons WHERE is_unknown = true")
            unknown_count = cur.fetchone()[0] + 1

            detected_at = datetime.now(timezone.utc)
            name = f"Desconocido #{unknown_count}"

            cur.execute(
                """INSERT INTO known_persons
                   (name, face_encoding, photo_url, is_active, is_unknown,
                    first_seen_camera_id, first_seen_at, times_seen, last_seen_at, notes)
                VALUES (%s, %s, %s, true, true, %s, %s, 1, %s, %s)
                RETURNING id""",
                (name, encoding_bytes, photo_url, camera_id, detected_at,
                 detected_at, "Detectado automaticamente por camara"),
            )
            person_id = str(cur.fetchone()[0])
        conn.close()

        # Add to in-memory cache
        with _known_persons_lock:
            _known_persons.append((person_id, name, embedding, True))

        _stats["unknowns_registered"] += 1
        logger.info(f"Auto-registered: {name} (id={person_id[:8]}, camera={camera_id})")
        return person_id

    except Exception as e:
        logger.error(f"Failed to register unknown: {e}")
        return None


def _update_unknown_seen(person_id: str):
    """Update times_seen for an existing unknown."""
    try:
        conn = _get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE known_persons SET times_seen = times_seen + 1, "
                "last_seen_at = NOW() WHERE id = %s",
                (person_id,),
            )
        conn.close()
    except Exception:
        pass


# ── FastAPI App ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load DeepFace models on startup."""
    _load_deepface()
    _refresh_known_persons()
    yield
    logger.info("Face Analyzer shutting down")


app = FastAPI(
    title="Deep Vision Face Analyzer",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "deepface_loaded": _deepface is not None,
        "model": settings.face_recognition_model,
        "detector": settings.face_detector_backend,
    }


@app.get("/stats")
async def stats():
    with _known_persons_lock:
        known_count = sum(1 for p in _known_persons if not p[3])
        unknown_count = sum(1 for p in _known_persons if p[3])
    return {
        **_stats,
        "known_persons": known_count,
        "unknown_persons": unknown_count,
    }


@app.post("/analyze")
async def analyze_face(
    image: UploadFile = File(...),
    bbox_x1: float = Form(0),
    bbox_y1: float = Form(0),
    bbox_x2: float = Form(0),
    bbox_y2: float = Form(0),
    camera_id: str = Form(""),
):
    """
    Analyze a frame for face detection and recognition.
    Expects the full frame with bbox coordinates for the person detection.
    """
    if _deepface is None:
        raise HTTPException(503, "DeepFace not loaded yet")

    _stats["faces_analyzed"] += 1
    _refresh_known_persons()

    # Decode image
    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(400, "Invalid image")

    h, w = frame.shape[:2]

    # If bbox provided, crop to person area with padding
    if bbox_x2 > 0 and bbox_y2 > 0:
        x1 = max(0, int(bbox_x1))
        y1 = max(0, int(bbox_y1))
        x2 = min(w, int(bbox_x2))
        y2 = min(h, int(bbox_y2))

        pad_w = int((x2 - x1) * 0.1)
        pad_h = int((y2 - y1) * 0.1)
        x1 = max(0, x1 - pad_w)
        y1 = max(0, y1 - pad_h)
        x2 = min(w, x2 + pad_w)
        y2 = min(h, y2 + pad_h)

        crop = frame[y1:y2, x1:x2]
    else:
        crop = frame

    if crop.size == 0 or crop.shape[0] < settings.face_min_size or crop.shape[1] < settings.face_min_size:
        return {"face_detected": False}

    # Detect face and extract embedding
    try:
        representations = _deepface.represent(
            crop,
            model_name=settings.face_recognition_model,
            detector_backend=settings.face_detector_backend,
            enforce_detection=False,
            align=True,
        )
    except Exception as e:
        logger.debug(f"DeepFace.represent failed: {e}")
        return {"face_detected": False}

    if not representations:
        return {"face_detected": False}

    face_data = representations[0]
    embedding = np.array(face_data["embedding"])
    face_confidence = face_data.get("face_confidence", 0.0)

    if face_confidence < 0.5:
        return {"face_detected": False}

    _stats["faces_detected"] += 1

    result = {
        "face_detected": True,
        "face_confidence": round(float(face_confidence), 3),
        "face_bbox": face_data.get("facial_area", {}),
    }

    # Match against known persons
    match = _find_match(embedding)
    if match:
        result["person_id"] = match[0]
        result["person_name"] = match[1]
        result["match_distance"] = match[2]
        result["is_unknown"] = match[3]

        if match[3]:
            _update_unknown_seen(match[0])
            _stats["faces_unknown"] += 1
        else:
            _stats["faces_matched"] += 1
            logger.info(f"Face matched: {match[1]} (distance={match[2]:.4f})")
    else:
        # Auto-register as Desconocido
        _stats["faces_unknown"] += 1
        unknown_id = _register_unknown(embedding, crop, camera_id)
        if unknown_id:
            result["person_id"] = unknown_id
            result["person_name"] = "Desconocido"
            result["is_unknown"] = True

    # Optionally analyze attributes
    if settings.face_analyze_attributes:
        try:
            analysis = _deepface.analyze(
                crop,
                actions=["age", "gender", "emotion"],
                detector_backend=settings.face_detector_backend,
                enforce_detection=False,
                silent=True,
            )
            if analysis:
                a = analysis[0]
                result["age"] = a.get("age")
                result["gender"] = a.get("dominant_gender")
                result["emotion"] = a.get("dominant_emotion")
        except Exception:
            pass

    return result


@app.post("/register")
async def register_person(
    name: str = Form(...),
    image: UploadFile = File(...),
    employee_id: str = Form(None),
    department: str = Form(None),
):
    """Register a new known person with their photo."""
    if _deepface is None:
        raise HTTPException(503, "DeepFace not loaded yet")

    contents = await image.read()
    nparr = np.frombuffer(contents, np.uint8)
    photo = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if photo is None:
        raise HTTPException(400, "Invalid image")

    try:
        representations = _deepface.represent(
            photo,
            model_name=settings.face_recognition_model,
            detector_backend=settings.face_detector_backend,
            enforce_detection=True,
            align=True,
        )
    except Exception as e:
        raise HTTPException(400, f"No face detected in photo: {e}")

    if not representations:
        raise HTTPException(400, "No face detected in photo")

    embedding = np.array(representations[0]["embedding"])
    face_confidence = representations[0].get("face_confidence", 0.0)
    encoding_bytes = pickle.dumps(embedding)

    # Upload photo to MinIO
    photo_url = ""
    try:
        minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_user,
            secret_key=settings.minio_password,
            secure=False,
        )
        bucket = "persons"
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)

        filename = f"{uuid.uuid4().hex}.jpg"
        _, buf = cv2.imencode(".jpg", photo, [cv2.IMWRITE_JPEG_QUALITY, 90])
        data = io.BytesIO(buf.tobytes())
        size = data.getbuffer().nbytes
        minio_client.put_object(bucket, filename, data, length=size,
                                 content_type="image/jpeg")
        photo_url = f"{bucket}/{filename}"
    except Exception as e:
        logger.warning(f"Failed to upload photo: {e}")

    # Save to database
    conn = _get_db_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO known_persons
               (name, employee_id, department, face_encoding, photo_url,
                is_active, is_unknown)
            VALUES (%s, %s, %s, %s, %s, true, false) RETURNING id""",
            (name, employee_id, department, encoding_bytes, photo_url),
        )
        person_id = str(cur.fetchone()[0])
    conn.close()

    # Force refresh cache
    global _last_db_refresh
    _last_db_refresh = 0
    _refresh_known_persons()

    logger.info(f"Registered: {name} (id={person_id})")
    return {
        "person_id": person_id,
        "name": name,
        "face_confidence": float(face_confidence),
        "embedding_size": len(embedding),
        "photo_url": photo_url,
    }


@app.get("/persons")
async def list_persons():
    """List all known persons (for cache inspection)."""
    _refresh_known_persons()
    with _known_persons_lock:
        return [
            {"person_id": p[0], "name": p[1], "is_unknown": p[3]}
            for p in _known_persons
        ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.service_port)
