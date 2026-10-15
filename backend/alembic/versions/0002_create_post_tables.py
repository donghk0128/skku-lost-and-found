"""Create categories and posts tables.

Revision ID: 0002_create_post_tables
Revises: 0001_create_auth_tables
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_create_post_tables"
down_revision = "0001_create_auth_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.SmallInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("post_type", sa.String(length=5), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("item_name", sa.String(length=100), nullable=True),
        sa.Column("category_id", sa.SmallInteger(), nullable=True),
        sa.Column("location_text", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("event_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=12), server_default="OPEN", nullable=False),
        sa.Column("creation_method", sa.String(length=12), server_default="MANUAL", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("post_type IN ('LOST', 'FOUND')", name="ck_posts_post_type"),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_posts_title_not_blank"),
        sa.CheckConstraint("length(trim(description)) > 0", name="ck_posts_description_not_blank"),
        sa.CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_posts_coordinates_together",
        ),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_posts_latitude_range"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_posts_longitude_range"),
        sa.CheckConstraint(
            "(event_start_at IS NULL AND event_end_at IS NULL) "
            "OR (event_start_at IS NOT NULL AND event_end_at IS NOT NULL AND event_start_at <= event_end_at)",
            name="ck_posts_event_range",
        ),
        sa.CheckConstraint("status IN ('OPEN', 'COMPLETED')", name="ck_posts_status"),
        sa.CheckConstraint("creation_method IN ('MANUAL', 'AI_ASSISTED')", name="ck_posts_creation_method"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("posts")
    op.drop_table("categories")
