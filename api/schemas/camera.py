import uuid
from datetime import datetime
from pydantic import BaseModel


class CameraCreate(BaseModel):
    name: str
    rtsp_url: str
    rtsp_sub_url: str | None = None
    brand: str | None = None
    model: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    config: dict | None = None


class CameraUpdate(BaseModel):
    name: str | None = None
    rtsp_url: str | None = None
    rtsp_sub_url: str | None = None
    brand: str | None = None
    model: str | None = None
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    enabled: bool | None = None
    recording_enabled: bool | None = None
    config: dict | None = None


class CameraResponse(BaseModel):
    id: uuid.UUID
    name: str
    rtsp_url: str
    rtsp_sub_url: str | None
    brand: str | None
    model: str | None
    location: str | None
    latitude: float | None
    longitude: float | None
    status: str
    enabled: bool
    recording_enabled: bool
    config: dict
    created_at: datetime

    class Config:
        from_attributes = True
