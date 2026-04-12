import uuid
from datetime import datetime
from pydantic import BaseModel


class EventsQuery(BaseModel):
    camera_id: uuid.UUID | None = None
    label: str | None = None
    event_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    review_pass: str | None = None
    limit: int = 50
    offset: int = 0


class EventResponse(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    zone_id: uuid.UUID | None
    event_type: str
    label: str
    confidence: float
    bbox: dict | None
    tracker_id: int | None
    snapshot_url: str | None
    clip_url: str | None
    thumbnail_url: str | None
    review_pass: str
    needs_deep_review: bool
    attributes: dict
    person_id: uuid.UUID | None
    detected_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True
