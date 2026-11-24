"""Push opt-in, session-bound devices and a transactional delivery outbox."""

from alembic import op
import sqlalchemy as sa

revision = "0016_push_notifications"
down_revision = "0015_keyword_conditions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("keyword_conditions", sa.Column("notification_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("keyword_conditions", sa.Column("notification_enabled_at", sa.DateTime(timezone=True)))
    op.create_table(
        "push_devices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("user_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fid", sa.String(128), nullable=False),
        sa.Column("fid_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("platform", sa.String(7), nullable=False),
        sa.Column("generation", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("platform IN ('android', 'ios')", name="ck_push_devices_platform"),
    )
    op.create_index("ix_push_devices_user_id", "push_devices", ["user_id"])
    op.create_table(
        "push_notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("post_id", sa.Uuid(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("condition_ids", sa.JSON(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "post_id", name="uq_push_notifications_user_post"),
    )
    op.create_table(
        "push_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("notification_id", sa.Uuid(), sa.ForeignKey("push_notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.Uuid(), sa.ForeignKey("push_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_generation", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(9), server_default="PENDING", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(64)),
        sa.UniqueConstraint("notification_id", "device_id", name="uq_push_deliveries_notification_device"),
        sa.CheckConstraint("status IN ('PENDING', 'SENT', 'CANCELLED', 'FAILED')", name="ck_push_deliveries_status"),
    )
    op.create_index("ix_push_deliveries_due", "push_deliveries", ["status", "next_attempt_at"])


def downgrade():
    op.drop_table("push_deliveries")
    op.drop_table("push_notifications")
    op.drop_table("push_devices")
    op.drop_column("keyword_conditions", "notification_enabled_at")
    op.drop_column("keyword_conditions", "notification_enabled")
