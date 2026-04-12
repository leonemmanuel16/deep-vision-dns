import uuid
from datetime import datetime
from pydantic import BaseModel


class ZoneCreate(BaseModel):
    camera_id: uuid.UUID
    name: str
    zone_type: str = "roi"
    points: list[dict]
    direction: str | None = None
    config: dict | None = None


class ZoneUpdate(BaseModel):
    name: str | None = None
    zone_type: str | None = None
    points: list[dict] | None = None
    direction: str | None = None
    config: dict | None = None
    enabled: bool | None = None


class ZoneResponse(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    name: str
    zone_type: str
    points: list[dict] | dict
    direction: str | None
    config: dict
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True
