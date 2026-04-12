import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from database import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("zones.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bbox: Mapped[dict | None] = mapped_column(JSONB)
    tracker_id: Mapped[int | None] = mapped_column(Integer)
    snapshot_url: Mapped[str | None] = mapped_column(String(500))
    clip_url: Mapped[str | None] = mapped_column(String(500))
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    review_pass: Mapped[str] = mapped_column(String(20), default="online")
    needs_deep_review: Mapped[bool] = mapped_column(Boolean, default=True)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    person_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
