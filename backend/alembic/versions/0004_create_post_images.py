"""Create post_images metadata table.

Revision ID: 0004_create_post_images
Revises: 0003_seed_post_categories
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_create_post_images"
down_revision = "0003_seed_post_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "post_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=30), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_post_images_position"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_post_images_post_id", "post_images", ["post_id"])


def downgrade() -> None:
    op.drop_index("ix_post_images_post_id", table_name="post_images")
    op.drop_table("post_images")
