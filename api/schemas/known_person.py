import uuid
from datetime import datetime
from pydantic import BaseModel


class PersonCreate(BaseModel):
    name: str
    employee_id: str | None = None
    department: str | None = None
    notes: str | None = None


class PersonUpdate(BaseModel):
    name: str | None = None
    employee_id: str | None = None
    department: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class PersonResponse(BaseModel):
    id: uuid.UUID
    name: str
    employee_id: str | None
    department: str | None
    photo_url: str | None
    notes: str | None
    is_active: bool
    is_unknown: bool = False
    has_face_encoding: bool = False
    first_seen_camera_id: uuid.UUID | None = None
    first_seen_at: datetime | None = None
    times_seen: int = 1
    last_seen_at: datetime | None = None
    merged_into_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MergeRequest(BaseModel):
    """Merge an unknown person into an existing known person."""
    target_person_id: uuid.UUID


class IdentifyRequest(BaseModel):
    """Assign identity to an unknown person."""
    name: str
    employee_id: str | None = None
    department: str | None = None
    notes: str | None = None
