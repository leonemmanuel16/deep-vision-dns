"""Known Persons endpoints — face database management."""

import io
import uuid
import pickle
from datetime import datetime, timezone

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from minio import Minio

from config import settings
from database import get_db
from models.known_person import KnownPerson
from schemas.known_person import PersonCreate, PersonUpdate, PersonResponse
from services.auth import get_current_user

router = APIRouter(prefix="/persons", tags=["persons"])

# DeepFace lazy import
_deepface_module = None


def _get_deepface():
    global _deepface_module
    if _deepface_module is None:
        try:
            from deepface import DeepFace
            _deepface_module = DeepFace
        except ImportError:
            pass
    return _deepface_module


def _get_minio():
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_user,
        secret_key=settings.minio_password,
        secure=False,
    )


def _person_to_response(person: KnownPerson) -> dict:
    """Convert KnownPerson model to response dict with has_face_encoding."""
    return {
        "id": person.id,
        "name": person.name,
        "employee_id": person.employee_id,
        "department": person.department,
        "photo_url": person.photo_url,
        "notes": person.notes,
        "is_active": person.is_active,
        "has_face_encoding": person.face_encoding is not None,
        "created_at": person.created_at,
        "updated_at": person.updated_at,
    }


@router.get("/", response_model=list[PersonResponse])
def list_persons(
    search: str | None = None,
    is_active: bool | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """List all known persons."""
    query = db.query(KnownPerson)

    if search:
        query = query.filter(
            KnownPerson.name.ilike(f"%{search}%")
            | KnownPerson.employee_id.ilike(f"%{search}%")
            | KnownPerson.department.ilike(f"%{search}%")
        )
    if is_active is not None:
        query = query.filter(KnownPerson.is_active == is_active)

    persons = query.order_by(desc(KnownPerson.created_at)).offset(offset).limit(limit).all()
    return [_person_to_response(p) for p in persons]


@router.get("/stats")
def person_stats(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get face database statistics."""
    from sqlalchemy import func

    total = db.query(func.count(KnownPerson.id)).scalar()
    active = db.query(func.count(KnownPerson.id)).filter(KnownPerson.is_active == True).scalar()
    with_encoding = db.query(func.count(KnownPerson.id)).filter(
        KnownPerson.face_encoding.isnot(None)
    ).scalar()

    return {
        "total": total,
        "active": active,
        "with_face_encoding": with_encoding,
        "without_face_encoding": total - with_encoding,
    }


@router.get("/{person_id}", response_model=PersonResponse)
def get_person(
    person_id: uuid.UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get a single known person."""
    person = db.query(KnownPerson).filter(KnownPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return _person_to_response(person)


@router.post("/", response_model=PersonResponse)
def create_person(
    data: PersonCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Create a new known person (without photo — use /upload-photo to add face)."""
    person = KnownPerson(
        name=data.name,
        employee_id=data.employee_id,
        department=data.department,
        notes=data.notes,
        is_active=True,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return _person_to_response(person)


@router.post("/register")
async def register_person_with_photo(
    name: str = Form(...),
    employee_id: str = Form(None),
    department: str = Form(None),
    notes: str = Form(None),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Register a new person WITH photo — extracts face embedding automatically.
    The photo must contain exactly one visible face.
    """
    DeepFace = _get_deepface()
    if DeepFace is None:
        raise HTTPException(
            status_code=503,
            detail="DeepFace not available on API server. Use detector service for face registration."
        )

    # Read photo
    contents = await photo.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    # Extract face embedding
    try:
        representations = DeepFace.represent(
            img,
            model_name="ArcFace",
            detector_backend="retinaface",
            enforce_detection=True,
            align=True,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No face detected in photo: {e}")

    if not representations:
        raise HTTPException(status_code=400, detail="No face detected in photo")

    embedding = np.array(representations[0]["embedding"])
    face_confidence = representations[0].get("face_confidence", 0.0)
    encoding_bytes = pickle.dumps(embedding)

    # Upload photo to MinIO
    photo_url = ""
    try:
        minio_client = _get_minio()
        bucket = "persons"
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)

        filename = f"{uuid.uuid4().hex}.jpg"
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        data = io.BytesIO(buf.tobytes())
        size = data.getbuffer().nbytes
        minio_client.put_object(bucket, filename, data, length=size, content_type="image/jpeg")
        photo_url = f"{bucket}/{filename}"
    except Exception:
        pass  # Photo upload is optional

    # Create person in DB
    person = KnownPerson(
        name=name,
        employee_id=employee_id,
        department=department,
        notes=notes,
        face_encoding=encoding_bytes,
        photo_url=photo_url,
        is_active=True,
    )
    db.add(person)
    db.commit()
    db.refresh(person)

    return {
        **_person_to_response(person),
        "face_confidence": round(float(face_confidence), 3),
        "embedding_size": len(embedding),
    }


@router.post("/{person_id}/upload-photo")
async def upload_person_photo(
    person_id: uuid.UUID,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Upload/update a person's photo and extract face embedding.
    Replaces existing encoding if present.
    """
    person = db.query(KnownPerson).filter(KnownPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    DeepFace = _get_deepface()
    if DeepFace is None:
        raise HTTPException(status_code=503, detail="DeepFace not available")

    contents = await photo.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file")

    try:
        representations = DeepFace.represent(
            img,
            model_name="ArcFace",
            detector_backend="retinaface",
            enforce_detection=True,
            align=True,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No face detected: {e}")

    embedding = np.array(representations[0]["embedding"])
    encoding_bytes = pickle.dumps(embedding)

    # Upload photo
    try:
        minio_client = _get_minio()
        bucket = "persons"
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
        filename = f"{uuid.uuid4().hex}.jpg"
        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        data = io.BytesIO(buf.tobytes())
        size = data.getbuffer().nbytes
        minio_client.put_object(bucket, filename, data, length=size, content_type="image/jpeg")
        person.photo_url = f"{bucket}/{filename}"
    except Exception:
        pass

    person.face_encoding = encoding_bytes
    person.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(person)

    return {
        **_person_to_response(person),
        "message": "Face encoding updated successfully",
        "embedding_size": len(embedding),
    }


@router.put("/{person_id}", response_model=PersonResponse)
def update_person(
    person_id: uuid.UUID,
    data: PersonUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Update a person's info (not photo)."""
    person = db.query(KnownPerson).filter(KnownPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(person, key, value)

    person.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(person)
    return _person_to_response(person)


@router.delete("/{person_id}")
def delete_person(
    person_id: uuid.UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Delete a person from the face database."""
    person = db.query(KnownPerson).filter(KnownPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    db.delete(person)
    db.commit()
    return {"message": "Person deleted", "id": str(person_id)}


@router.get("/{person_id}/events")
def get_person_events(
    person_id: uuid.UUID,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get recent events where this person was detected."""
    from models.event import Event

    events = (
        db.query(Event)
        .filter(Event.person_id == person_id)
        .order_by(desc(Event.detected_at))
        .limit(limit)
        .all()
    )
    return events
