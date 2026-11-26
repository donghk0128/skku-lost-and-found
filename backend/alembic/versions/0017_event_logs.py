"""Collect bounded service usage events."""

from alembic import op
import sqlalchemy as sa

revision = "0017_event_logs"
down_revision = "0016_push_notifications"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "event_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("visit_id", sa.Uuid()),
        sa.Column("post_id", sa.Uuid()),
        sa.Column("source_post_id", sa.Uuid()),
        sa.Column("candidate_post_id", sa.Uuid()),
        sa.Column("run_id", sa.Uuid()),
        sa.Column("rank", sa.Integer()),
        sa.Column("properties", sa.JSON(), nullable=False),
    )
    op.create_index("ix_event_logs_type_received", "event_logs", ["event_type", "received_at"])
    op.create_index("ix_event_logs_user_received", "event_logs", ["user_id", "received_at"])


def downgrade():
    op.drop_table("event_logs")
