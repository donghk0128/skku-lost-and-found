"""Record explicit color conflicts in recommendation results.

Revision ID: 0009_record_color_conflict
Revises: 0008_create_recommendation_runs
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_record_color_conflict"
down_revision = "0008_create_recommendation_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recommendation_items",
        sa.Column("color_conflict", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("recommendation_items", "color_conflict")
