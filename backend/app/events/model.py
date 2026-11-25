"""Bounded, privacy-conscious service usage events."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class EventLog(Base):
    __tablename__ = "event_logs"
    __table_args__ = (
        Index("ix_event_logs_type_received", "event_type", "received_at"),
        Index("ix_event_logs_user_received", "user_id", "received_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    visit_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    post_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    source_post_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    candidate_post_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    run_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    rank: Mapped[int | None] = mapped_column(Integer)
    properties: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
