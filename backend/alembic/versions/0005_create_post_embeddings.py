"""Store Gemini post embeddings with pgvector.

Revision ID: 0005_create_post_embeddings
Revises: 0004_create_post_images
"""

from alembic import op
from pgvector.sqlalchemy import VECTOR
import sqlalchemy as sa


revision = "0005_create_post_embeddings"
down_revision = "0004_create_post_images"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")
    # Supabase commonly installs vector in extensions; local Postgres starts empty.
    op.execute("SET LOCAL search_path TO public, extensions")
    op.create_table(
        "post_embeddings",
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", VECTOR(768), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id"),
    )


def downgrade() -> None:
    op.drop_table("post_embeddings")
    # Keep the extension; another table or service may use it.

