"""Event endpoints."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models.event import Event
from schemas.event import EventResponse
from services.auth import get_current_user

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=list[EventResponse])
def list_events(
    camera_id: uuid.UUID | None = None,
    label: str | None = None,
    event_type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    review_pass: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(Event)

    if camera_id:
        query = query.filter(Event.camera_id == camera_id)
    if label:
        query = query.filter(Event.label == label)
    if event_type:
        query = query.filter(Event.event_type == event_type)
    if start_date:
        query = query.filter(Event.detected_at >= start_date)
    if end_date:
        query = query.filter(Event.detected_at <= end_date)
    if review_pass:
        query = query.filter(Event.review_pass == review_pass)

    return query.order_by(desc(Event.detected_at)).offset(offset).limit(limit).all()


@router.get("/stats")
def event_stats(
    hours: int = Query(default=24, le=168),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get event statistics for the last N hours."""
    from sqlalchemy import func, text
    from datetime import timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    total = db.query(func.count(Event.id)).filter(Event.detected_at >= cutoff).scalar()

    by_type = (
        db.query(Event.event_type, func.count(Event.id))
        .filter(Event.detected_at >= cutoff)
        .group_by(Event.event_type)
        .all()
    )

    by_camera = (
        db.query(Event.camera_id, func.count(Event.id))
        .filter(Event.detected_at >= cutoff)
        .group_by(Event.camera_id)
        .order_by(desc(func.count(Event.id)))
        .limit(10)
        .all()
    )

    by_label = (
        db.query(Event.label, func.count(Event.id))
        .filter(Event.detected_at >= cutoff)
        .group_by(Event.label)
        .all()
    )

    return {
        "total": total,
        "by_type": {t: c for t, c in by_type},
        "by_camera": {str(cam): c for cam, c in by_camera},
        "by_label": {l: c for l, c in by_label},
        "hours": hours,
    }


@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
