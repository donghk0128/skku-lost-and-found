"""Stored text embeddings for posts."""

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint, func
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


class RecommendationRun(Base):
    __tablename__ = "recommendation_runs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    source_post_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("posts.id"), nullable=False, index=True)
    algorithm_version: Mapped[str] = mapped_column(String(40), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"
    __table_args__ = (UniqueConstraint("run_id", "rank", name="uq_recommendation_items_run_rank"),)

    run_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE"), primary_key=True)
    candidate_post_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("posts.id"), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    rule_score: Mapped[float] = mapped_column(Float, nullable=False)
    semantic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_score: Mapped[float] = mapped_column(Float, nullable=False)
    category_score: Mapped[float] = mapped_column(Float, nullable=False)
    time_score: Mapped[float] = mapped_column(Float, nullable=False)
    location_score: Mapped[float] = mapped_column(Float, nullable=False)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_gap_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)

