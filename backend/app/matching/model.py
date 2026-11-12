"""Stored text embeddings for posts."""

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class PostEmbedding(Base):
    __tablename__ = "post_embeddings"

    post_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # SQLite can store test fixtures as JSON; actual vector queries run in PostgreSQL.
    embedding: Mapped[list[float]] = mapped_column(
        VECTOR(768).with_variant(JSON(), "sqlite"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

