"""Database tables for lost and found posts."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint("post_type IN ('LOST', 'FOUND')", name="ck_posts_post_type"),
        CheckConstraint("length(trim(title)) > 0", name="ck_posts_title_not_blank"),
        CheckConstraint("length(trim(description)) > 0", name="ck_posts_description_not_blank"),
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_posts_coordinates_together",
        ),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_posts_latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_posts_longitude_range"),
        CheckConstraint(
            "(event_start_at IS NULL AND event_end_at IS NULL) "
            "OR (event_start_at IS NOT NULL AND event_end_at IS NOT NULL AND event_start_at <= event_end_at)",
            name="ck_posts_event_range",
        ),
        CheckConstraint("status IN ('OPEN', 'COMPLETED')", name="ck_posts_status"),
        CheckConstraint("creation_method IN ('MANUAL', 'AI_ASSISTED')", name="ck_posts_creation_method"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    post_type: Mapped[str] = mapped_column(String(5), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    item_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_id: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("categories.id"), nullable=True)
    location_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    event_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="OPEN", server_default="OPEN")
    creation_method: Mapped[str] = mapped_column(String(12), nullable=False, default="MANUAL", server_default="MANUAL")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc, onupdate=now_utc, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PostImage(Base):
    __tablename__ = "post_images"
    __table_args__ = (CheckConstraint("position >= 0", name="ck_post_images_position"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("posts.id"), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc, server_default=func.now())
