"""Store two-party confirmed lost/found post pairs."""

from alembic import op
import sqlalchemy as sa

revision = "0018_return_pairs"
down_revision = "0017_event_logs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "return_pairs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("room_id", sa.Uuid(), sa.ForeignKey("chat_rooms.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("lost_post_id", sa.Uuid(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("found_post_id", sa.Uuid(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposed_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(9), server_default="PENDING", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("lost_post_id <> found_post_id", name="ck_return_pairs_distinct_posts"),
        sa.CheckConstraint("status IN ('PENDING', 'CONFIRMED')", name="ck_return_pairs_status"),
    )


def downgrade():
    op.drop_table("return_pairs")
