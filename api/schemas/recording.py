import uuid
from datetime import datetime
from pydantic import BaseModel


class RecordingResponse(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    file_path: str
    start_time: datetime
    end_time: datetime | None
    duration_seconds: int | None
    file_size_bytes: int | None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
