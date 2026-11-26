"""Durable outbox; one notification per account/post, one delivery per device."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func, true
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.users.model import now_utc


class PushDevice(Base):
    __tablename__ = "push_devices"
    __table_args__ = (CheckConstraint("platform IN ('android', 'ios')", name="ck_push_devices_platform"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("user_sessions.id", ondelete="CASCADE"), nullable=False)
    # FCM's current registration API uses a Firebase Installation ID (FID).
    fid: Mapped[str] = mapped_column(String(128), nullable=False)
    fid_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(7), nullable=False)
    generation: Mapped[UUID] = mapped_column(Uuid, nullable=False, default=uuid4)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc, server_default=func.now())


class PushNotification(Base):
    __tablename__ = "push_notifications"
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_push_notifications_user_post"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    post_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    condition_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc, server_default=func.now())


class PushDelivery(Base):
    __tablename__ = "push_deliveries"
    __table_args__ = (
        UniqueConstraint("notification_id", "device_id", name="uq_push_deliveries_notification_device"),
        CheckConstraint("status IN ('PENDING', 'SENT', 'CANCELLED', 'FAILED')", name="ck_push_deliveries_status"),
        Index("ix_push_deliveries_due", "status", "next_attempt_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    notification_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("push_notifications.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("push_devices.id", ondelete="CASCADE"), nullable=False)
    device_generation: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(9), nullable=False, default="PENDING", server_default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc, server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(64))


class ChatPushNotification(Base):
    __tablename__ = "chat_push_notifications"
    __table_args__ = (UniqueConstraint("user_id", "message_id", name="uq_chat_push_user_message"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    room_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False)
    message_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc, server_default=func.now())


class ChatPushDelivery(Base):
    __tablename__ = "chat_push_deliveries"
    __table_args__ = (
        UniqueConstraint("notification_id", "device_id", name="uq_chat_push_delivery_device"),
        CheckConstraint("status IN ('PENDING', 'SENT', 'CANCELLED', 'FAILED')", name="ck_chat_push_delivery_status"),
        Index("ix_chat_push_deliveries_due", "status", "next_attempt_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    notification_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("chat_push_notifications.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("push_devices.id", ondelete="CASCADE"), nullable=False)
    device_generation: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(9), nullable=False, default="PENDING", server_default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc, server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(64))
