"""Durable, per-message chat push work."""

from alembic import op
import sqlalchemy as sa

revision = "0019_chat_push_notifications"
down_revision = "0018_return_pairs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chat_push_notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_id", sa.Uuid(), sa.ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "message_id", name="uq_chat_push_user_message"),
    )
    op.create_table(
        "chat_push_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("notification_id", sa.Uuid(), sa.ForeignKey("chat_push_notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.Uuid(), sa.ForeignKey("push_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_generation", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(9), server_default="PENDING", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(64)),
        sa.UniqueConstraint("notification_id", "device_id", name="uq_chat_push_delivery_device"),
        sa.CheckConstraint("status IN ('PENDING', 'SENT', 'CANCELLED', 'FAILED')", name="ck_chat_push_delivery_status"),
    )
    op.create_index("ix_chat_push_deliveries_due", "chat_push_deliveries", ["status", "next_attempt_at"])


def downgrade():
    op.drop_table("chat_push_deliveries")
    op.drop_table("chat_push_notifications")
