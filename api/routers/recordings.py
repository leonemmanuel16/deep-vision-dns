"""Recordings endpoints."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models.recording import Recording
from schemas.recording import RecordingResponse
from services.auth import get_current_user

router = APIRouter(prefix="/recordings", tags=["recordings"])


@router.get("/", response_model=list[RecordingResponse])
def list_recordings(
    camera_id: uuid.UUID | None = None,
    date: datetime | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(Recording)
    if camera_id:
        query = query.filter(Recording.camera_id == camera_id)
    if date:
        query = query.filter(
            Recording.start_time >= date.replace(hour=0, minute=0, second=0),
            Recording.start_time < date.replace(hour=23, minute=59, second=59),
        )
    return query.order_by(desc(Recording.start_time)).offset(offset).limit(limit).all()


@router.get("/{recording_id}", response_model=RecordingResponse)
def get_recording(recording_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    return recording


@router.get("/timeline/{camera_id}")
def get_timeline(
    camera_id: uuid.UUID,
    date: datetime | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get 24h timeline of recordings for a camera on a given date."""
    from datetime import timedelta, timezone

    if not date:
        date = datetime.now(timezone.utc)

    start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    recordings = (
        db.query(Recording)
        .filter(
            Recording.camera_id == camera_id,
            Recording.start_time >= start,
            Recording.start_time < end,
        )
        .order_by(Recording.start_time)
        .all()
    )

    segments = []
    for rec in recordings:
        segments.append({
            "id": str(rec.id),
            "start": rec.start_time.isoformat(),
            "end": rec.end_time.isoformat() if rec.end_time else None,
            "duration": rec.duration_seconds,
            "status": rec.status,
        })

    return {"camera_id": str(camera_id), "date": start.isoformat(), "segments": segments}
