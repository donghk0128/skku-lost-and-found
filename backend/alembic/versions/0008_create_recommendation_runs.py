"""Record reproducible recommendation rankings and component scores.

Revision ID: 0008_create_recommendation_runs
Revises: 0007_create_chat_message_images
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_create_recommendation_runs"
down_revision = "0007_create_chat_message_images"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_post_id", sa.Uuid(), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("algorithm_version", sa.String(40), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recommendation_runs_source_post_id", "recommendation_runs", ["source_post_id"])
    op.create_table(
        "recommendation_items",
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("recommendation_runs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("candidate_post_id", sa.Uuid(), sa.ForeignKey("posts.id"), primary_key=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("rule_score", sa.Float(), nullable=False),
        sa.Column("semantic_score", sa.Float(), nullable=True),
        sa.Column("text_score", sa.Float(), nullable=False),
        sa.Column("category_score", sa.Float(), nullable=False),
        sa.Column("time_score", sa.Float(), nullable=False),
        sa.Column("location_score", sa.Float(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("time_gap_hours", sa.Float(), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.UniqueConstraint("run_id", "rank", name="uq_recommendation_items_run_rank"),
    )


def downgrade() -> None:
    op.drop_table("recommendation_items")
    op.drop_index("ix_recommendation_runs_source_post_id", table_name="recommendation_runs")
    op.drop_table("recommendation_runs")
