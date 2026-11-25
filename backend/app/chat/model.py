"""Chat persistence; message sequence is assigned under the post row lock."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base
from app.posts.model import now_utc


class ChatRoom(Base):
    __tablename__ = "chat_rooms"
    __table_args__ = (
        UniqueConstraint("post_id", "requester_id", name="uq_chat_rooms_post_requester"),
        CheckConstraint("owner_id <> requester_id", name="ck_chat_rooms_distinct_users"),
        CheckConstraint("status = 'CLOSED' OR (post_id IS NOT NULL AND owner_id IS NOT NULL AND requester_id IS NOT NULL)", name="ck_chat_rooms_active_references"),
        CheckConstraint(
            "(status = 'ACTIVE' AND close_reason IS NULL AND closed_at IS NULL) OR "
            "(status = 'CLOSED' AND close_reason IS NOT NULL AND close_reason IN ('RETURNED', 'GENERAL', 'POST_COMPLETED') AND closed_at IS NOT NULL)",
            name="ck_chat_rooms_lifecycle",
        ),
        Index("ix_chat_rooms_post_status", "post_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    requester_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(6), default="ACTIVE", server_default="ACTIVE", nullable=False)
    close_reason: Mapped[str | None] = mapped_column(String(14))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, server_default=func.now(), nullable=False)


class ReturnPair(Base):
    """A ground-truth pair only after the other chat participant confirms it."""

    __tablename__ = "return_pairs"
    __table_args__ = (
        CheckConstraint("lost_post_id <> found_post_id", name="ck_return_pairs_distinct_posts"),
        CheckConstraint("status IN ('PENDING', 'CONFIRMED')", name="ck_return_pairs_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("chat_rooms.id", ondelete="CASCADE"), unique=True, nullable=False)
    lost_post_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    found_post_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    proposed_by_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(9), default="PENDING", server_default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, server_default=func.now(), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChatRoomMember(Base):
    __tablename__ = "chat_room_members"
    __table_args__ = (
        CheckConstraint("last_read_sequence >= 0", name="ck_chat_members_read_sequence"),
        Index("ix_chat_room_members_user_hidden", "user_id", "is_hidden"),
    )
    room_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("chat_rooms.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    last_read_sequence: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, server_default=func.now(), nullable=False)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("room_id", "sequence", name="uq_chat_messages_room_sequence"),
        UniqueConstraint("room_id", "sender_id", "client_message_id", name="uq_chat_messages_client_message"),
        CheckConstraint("sequence > 0", name="ck_chat_messages_sequence"),
        CheckConstraint(
            "(message_type = 'TEXT' AND content IS NOT NULL AND length(trim(content)) BETWEEN 1 AND 2000) OR "
            "(message_type = 'IMAGE' AND (content IS NULL OR length(trim(content)) BETWEEN 1 AND 2000))",
            name="ck_chat_messages_payload",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("chat_rooms.id"), nullable=False)
    sender_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    message_type: Mapped[str] = mapped_column(String(5), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    client_message_id: Mapped[str | None] = mapped_column(String(64))
    upload_fingerprint: Mapped[str | None] = mapped_column(String(64))
    images: Mapped[list["ChatMessageImage"]] = relationship(
        order_by="ChatMessageImage.position", lazy="selectin", cascade="all, delete-orphan",
        passive_deletes=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, server_default=func.now(), nullable=False)


class ChatMessageImage(Base):
    __tablename__ = "chat_message_images"
    __table_args__ = (
        UniqueConstraint("message_id", "position", name="uq_chat_message_images_position"),
        CheckConstraint("position >= 0", name="ck_chat_message_images_position"),
        CheckConstraint("content_type IN ('image/jpeg', 'image/png', 'image/webp')", name="ck_chat_message_images_type"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
