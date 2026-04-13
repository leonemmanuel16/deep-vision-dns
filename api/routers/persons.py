"""Known Persons endpoints — face database management with unknown auto-registration."""

import io
import uuid
import pickle
from datetime import datetime, timezone

import cv2
import numpy as np
import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from minio import Minio

from config import settings
from database import get_db
from models.known_person import KnownPerson
from models.event import Event
from schemas.known_person import (
    PersonCreate, PersonUpdate, PersonResponse,
    MergeRequest, IdentifyRequest,
)
from services.auth import get_current_user

router = APIRouter(prefix="/persons", tags=["persons"])

# Face-analyzer microservice URL
FACE_ANALYZER_URL = getattr(settings, 'face_analyzer_url', 'http://face-analyzer:8002')


def _get_minio():
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_user,
        secret_key=settings.minio_password,
        secure=False,
    )


def _person_to_response(person: KnownPerson) -> dict:
    return {
        "id": person.id,
        "name": person.name,
        "employee_id": person.employee_id,
        "department": person.department,
        "photo_url": person.photo_url,
        "notes": person.notes,
        "is_active": person.is_active,
        "is_unknown": person.is_unknown or False,
        "has_face_encoding": person.face_encoding is not None,
        "first_seen_camera_id": person.first_seen_camera_id,
        "first_seen_at": person.first_seen_at,
        "times_seen": person.times_seen or 1,
        "last_seen_at": person.last_seen_at,
        "merged_into_id": person.merged_into_id,
        "created_at": person.created_at,
        "updated_at": person.updated_at,
    }


# ═══════════════════════════════════════════════════════════════
# LIST / SEARCH
# ═══════════════════════════════════════════════════════════════

@router.get("/", response_model=list[PersonResponse])
def list_persons(
    search: str | None = None,
    is_active: bool | None = None,
    is_unknown: bool | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """List persons. Filter by is_unknown=true to see only unknowns."""
    query = db.query(KnownPerson).filter(KnownPerson.merged_into_id.is_(None))

    if search:
        query = query.filter(
            KnownPerson.name.ilike(f"%{search}%")
            | KnownPerson.employee_id.ilike(f"%{search}%")
            | KnownPerson.department.ilike(f"%{search}%")
        )
    if is_active is not None:
        query = query.filter(KnownPerson.is_active == is_active)
    if is_unknown is not None:
        query = query.filter(KnownPerson.is_unknown == is_unknown)

    persons = query.order_by(desc(KnownPerson.created_at)).offset(offset).limit(limit).all()
    return [_person_to_response(p) for p in persons]


@router.get("/stats")
def person_stats(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get face database statistics."""
    total = db.query(func.count(KnownPerson.id)).filter(
        KnownPerson.merged_into_id.is_(None)
    ).scalar()
    active = db.query(func.count(KnownPerson.id)).filter(
        KnownPerson.is_active == True,
        KnownPerson.merged_into_id.is_(None),
    ).scalar()
    known = db.query(func.count(KnownPerson.id)).filter(
        KnownPerson.is_unknown == False,
        KnownPerson.merged_into_id.is_(None),
    ).scalar()
    unknowns = db.query(func.count(KnownPerson.id)).filter(
        KnownPerson.is_unknown == True,
        KnownPerson.merged_into_id.is_(None),
    ).scalar()
    with_encoding = db.query(func.count(KnownPerson.id)).filter(
        KnownPerson.face_encoding.isnot(None),
        KnownPerson.merged_into_id.is_(None),
    ).scalar()

    return {
        "total": total,
        "active": active,
        "known": known,
        "unknowns": unknowns,
        "with_face_encoding": with_encoding,
        "without_face_encoding": total - with_encoding,
    }


@router.get("/unknowns", response_model=list[PersonResponse])
def list_unknowns(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """List only unknown/unidentified persons, sorted by most recently seen."""
    persons = (
        db.query(KnownPerson)
        .filter(
            KnownPerson.is_unknown == True,
            KnownPerson.is_active == True,
            KnownPerson.merged_into_id.is_(None),
        )
        .order_by(desc(KnownPerson.last_seen_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_person_to_response(p) for p in persons]


# ═══════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════

@router.get("/{person_id}", response_model=PersonResponse)
def get_person(
    person_id: uuid.UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
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
    person = KnownPerson(
        name=data.name,
        employee_id=data.employee_id,
        department=data.department,
        notes=data.notes,
        is_active=True,
        is_unknown=False,
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
    """Register a new known person WITH photo — sends to face-analyzer microservice."""
    contents = await photo.read()

    # Send to face-analyzer microservice for registration
    try:
        resp = http_requests.post(
            f"{FACE_ANALYZER_URL}/register",
            files={"image": ("photo.jpg", io.BytesIO(contents), "image/jpeg")},
            data={"name": name, "employee_id": employee_id or "", "department": department or ""},
            timeout=30,
        )
        if resp.status_code != 200:
            error = resp.json().get("detail", "Face analysis failed")
            raise HTTPException(status_code=resp.status_code, detail=error)

        result = resp.json()
        person_id = result.get("person_id")

        # Fetch the created person from DB
        person = db.query(KnownPerson).filter(KnownPerson.id == person_id).first()
        if person:
            if notes:
                person.notes = notes
                db.commit()
                db.refresh(person)
            return {
                **_person_to_response(person),
                "face_confidence": result.get("face_confidence", 0.0),
                "embedding_size": result.get("embedding_size", 0),
            }
        else:
            return result

    except http_requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Face analyzer service unavailable")
    except http_requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Face analyzer service timeout")


@router.post("/{person_id}/upload-photo")
async def upload_person_photo(
    person_id: uuid.UUID,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Upload/update a person's photo — sends to face-analyzer for embedding extraction."""
    person = db.query(KnownPerson).filter(KnownPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    contents = await photo.read()

    # Use face-analyzer service to extract embedding
    try:
        resp = http_requests.post(
            f"{FACE_ANALYZER_URL}/analyze",
            files={"image": ("photo.jpg", io.BytesIO(contents), "image/jpeg")},
            data={"bbox_x1": "0", "bbox_y1": "0", "bbox_x2": "0", "bbox_y2": "0"},
            timeout=30,
        )
    except (http_requests.exceptions.ConnectionError, http_requests.exceptions.Timeout):
        raise HTTPException(status_code=503, detail="Face analyzer service unavailable")

    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Face analysis failed")

    # Upload photo to MinIO
    try:
        minio_client = _get_minio()
        bucket = "persons"
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
        filename = f"{uuid.uuid4().hex}.jpg"
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            data = io.BytesIO(buf.tobytes())
            size = data.getbuffer().nbytes
            minio_client.put_object(bucket, filename, data, length=size, content_type="image/jpeg")
            person.photo_url = f"{bucket}/{filename}"
    except Exception:
        pass

    person.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(person)

    return {**_person_to_response(person), "message": "Photo updated"}


@router.put("/{person_id}", response_model=PersonResponse)
def update_person(
    person_id: uuid.UUID,
    data: PersonUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
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
    person = db.query(KnownPerson).filter(KnownPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    db.delete(person)
    db.commit()
    return {"message": "Person deleted", "id": str(person_id)}


# ═══════════════════════════════════════════════════════════════
# IDENTIFY & MERGE (for unknowns)
# ═══════════════════════════════════════════════════════════════

@router.post("/{person_id}/identify", response_model=PersonResponse)
def identify_unknown(
    person_id: uuid.UUID,
    data: IdentifyRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Assign identity to an unknown person.
    Changes them from "Desconocido" to a named known person.
    Keeps the same face embedding so future detections match correctly.
    """
    person = db.query(KnownPerson).filter(KnownPerson.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    if not person.is_unknown:
        raise HTTPException(status_code=400, detail="Person is already identified")

    person.name = data.name
    person.is_unknown = False
    if data.employee_id:
        person.employee_id = data.employee_id
    if data.department:
        person.department = data.department
    if data.notes:
        person.notes = data.notes
    person.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(person)
    return _person_to_response(person)


@router.post("/{person_id}/merge", response_model=PersonResponse)
def merge_into_existing(
    person_id: uuid.UUID,
    data: MergeRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Merge an unknown person into an existing known person.

    - Updates all events that reference the unknown person_id → target_person_id
    - Marks the unknown as merged (merged_into_id) and inactive
    - The target person keeps their existing face encoding
    - Future detections will match the target person directly
    """
    # Validate source (unknown)
    source = db.query(KnownPerson).filter(KnownPerson.id == person_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source person not found")

    # Validate target (existing)
    target = db.query(KnownPerson).filter(KnownPerson.id == data.target_person_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target person not found")

    if str(source.id) == str(target.id):
        raise HTTPException(status_code=400, detail="Cannot merge person into themselves")

    # Update all events: source → target
    updated_events = (
        db.query(Event)
        .filter(Event.person_id == person_id)
        .update({Event.person_id: data.target_person_id})
    )

    # Mark source as merged + inactive
    source.merged_into_id = data.target_person_id
    source.is_active = False
    source.is_unknown = False
    source.notes = (
        f"Fusionado con {target.name} (ID: {str(target.id)[:8]}). "
        f"{updated_events} eventos transferidos."
    )
    source.updated_at = datetime.now(timezone.utc)

    # Update target's times_seen
    if source.times_seen and target.times_seen:
        target.times_seen = (target.times_seen or 0) + (source.times_seen or 0)
    target.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(target)

    return _person_to_response(target)


@router.get("/{person_id}/events")
def get_person_events(
    person_id: uuid.UUID,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get recent events where this person was detected."""
    events = (
        db.query(Event)
        .filter(Event.person_id == person_id)
        .order_by(desc(Event.detected_at))
        .limit(limit)
        .all()
    )
    return events
