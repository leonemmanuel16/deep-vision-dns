import uuid
from datetime import datetime
from pydantic import BaseModel


class AlertRuleCreate(BaseModel):
    name: str
    event_type: str
    camera_ids: list[uuid.UUID] | None = None
    zone_ids: list[uuid.UUID] | None = None
    conditions: dict | None = None
    actions: list[dict]
    cooldown_seconds: int = 60


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    event_type: str | None = None
    camera_ids: list[uuid.UUID] | None = None
    zone_ids: list[uuid.UUID] | None = None
    conditions: dict | None = None
    actions: list[dict] | None = None
    cooldown_seconds: int | None = None
    enabled: bool | None = None


class AlertRuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    event_type: str
    camera_ids: list[uuid.UUID] | None
    zone_ids: list[uuid.UUID] | None
    conditions: dict
    actions: dict | list
    cooldown_seconds: int
    enabled: bool
    last_triggered_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True
