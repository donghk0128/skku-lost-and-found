"""Create private chat rooms, membership and messages.

Revision ID: 0006_create_chat_tables
Revises: 0005_create_post_embeddings
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_create_chat_tables"
down_revision = "0005_create_post_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_rooms",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("post_id", sa.Uuid(), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("requester_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(6), server_default="ACTIVE", nullable=False),
        sa.Column("close_reason", sa.String(14)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("post_id", "requester_id", name="uq_chat_rooms_post_requester"),
        sa.CheckConstraint("owner_id <> requester_id", name="ck_chat_rooms_distinct_users"),
        sa.CheckConstraint(
            "(status = 'ACTIVE' AND close_reason IS NULL AND closed_at IS NULL) OR "
            "(status = 'CLOSED' AND close_reason IS NOT NULL AND close_reason IN ('RETURNED', 'GENERAL', 'POST_COMPLETED') AND closed_at IS NOT NULL)",
            name="ck_chat_rooms_lifecycle"),
    )
    op.create_index("ix_chat_rooms_post_status", "chat_rooms", ["post_id", "status"])
    op.create_table(
        "chat_room_members",
        sa.Column("room_id", sa.Uuid(), sa.ForeignKey("chat_rooms.id"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("last_read_sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True)),
        sa.Column("is_hidden", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("last_read_sequence >= 0", name="ck_chat_members_read_sequence"),
    )
    op.create_index("ix_chat_room_members_user_hidden", "chat_room_members", ["user_id", "is_hidden"])
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("room_id", sa.Uuid(), sa.ForeignKey("chat_rooms.id"), nullable=False),
        sa.Column("sender_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("message_type", sa.String(5), nullable=False),
        sa.Column("content", sa.Text()),
        sa.Column("image_storage_key", sa.String(255), unique=True),
        sa.Column("image_content_type", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("room_id", "sequence", name="uq_chat_messages_room_sequence"),
        sa.CheckConstraint("sequence > 0", name="ck_chat_messages_sequence"),
        sa.CheckConstraint(
            "(message_type = 'TEXT' AND content IS NOT NULL AND length(trim(content)) BETWEEN 1 AND 2000 "
            "AND image_storage_key IS NULL AND image_content_type IS NULL) OR "
            "(message_type = 'IMAGE' AND content IS NULL AND image_storage_key IS NOT NULL "
            "AND image_content_type IS NOT NULL AND image_content_type IN ('image/jpeg', 'image/png', 'image/webp'))", name="ck_chat_messages_payload"),
    )


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_room_members_user_hidden", table_name="chat_room_members")
    op.drop_table("chat_room_members")
    op.drop_index("ix_chat_rooms_post_status", table_name="chat_rooms")
    op.drop_table("chat_rooms")
