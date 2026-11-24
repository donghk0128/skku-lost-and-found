"""Store account-owned, versioned keyword condition snapshots.

Revision ID: 0015_keyword_conditions
Revises: 0014_post_location_limit_policy
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_keyword_conditions"
down_revision = "0014_post_location_limit_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "keyword_conditions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("post_type", sa.String(5), nullable=False),
        sa.Column("version", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("post_type IN ('LOST', 'FOUND')", name="ck_keyword_conditions_post_type"),
        sa.CheckConstraint("version = 1", name="ck_keyword_conditions_version"),
    )
    op.create_index("ix_keyword_conditions_user_id", "keyword_conditions", ["user_id"])


def downgrade() -> None:
    op.drop_table("keyword_conditions")
