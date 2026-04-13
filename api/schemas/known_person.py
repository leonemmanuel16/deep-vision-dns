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
    has_face_encoding: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
