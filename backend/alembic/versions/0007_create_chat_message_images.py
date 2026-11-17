"""Move existing chat images into an ordered attachment table without moving files."""

from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0007_create_chat_message_images"
down_revision = "0006_create_chat_tables"
branch_labels = None
depends_on = None

PAYLOAD = (
    "(message_type = 'TEXT' AND content IS NOT NULL AND length(trim(content)) BETWEEN 1 AND 2000) OR "
    "(message_type = 'IMAGE' AND (content IS NULL OR length(trim(content)) BETWEEN 1 AND 2000))"
)


def upgrade() -> None:
    images = op.create_table(
        "chat_message_images",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False, unique=True),
        sa.Column("content_type", sa.String(30), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("message_id", "position", name="uq_chat_message_images_position"),
        sa.CheckConstraint("position >= 0", name="ck_chat_message_images_position"),
        sa.CheckConstraint("content_type IN ('image/jpeg', 'image/png', 'image/webp')", name="ck_chat_message_images_type"),
    )
    connection = op.get_bind()
    old = connection.execute(sa.text(
        "SELECT id, image_storage_key, image_content_type FROM chat_messages WHERE message_type = 'IMAGE'"
    )).mappings()
    for row in old:
        connection.execute(images.insert().values(
            id=uuid4(), message_id=row["id"], storage_key=row["image_storage_key"],
            content_type=row["image_content_type"], position=0,
        ))
    op.drop_constraint("ck_chat_messages_payload", "chat_messages", type_="check")
    op.drop_column("chat_messages", "image_storage_key")
    op.drop_column("chat_messages", "image_content_type")
    op.add_column("chat_messages", sa.Column("client_message_id", sa.String(64)))
    op.add_column("chat_messages", sa.Column("upload_fingerprint", sa.String(64)))
    op.create_unique_constraint("uq_chat_messages_client_message", "chat_messages", ["room_id", "sender_id", "client_message_id"])
    op.create_check_constraint("ck_chat_messages_payload", "chat_messages", PAYLOAD)


def downgrade() -> None:
    connection = op.get_bind()
    incompatible = connection.scalar(sa.text(
        "SELECT count(*) FROM chat_messages m WHERE m.message_type = 'IMAGE' AND "
        "(m.content IS NOT NULL OR (SELECT count(*) FROM chat_message_images i WHERE i.message_id = m.id) <> 1)"
    ))
    if incompatible:
        raise RuntimeError("Cannot downgrade: grouped/captioned messages would lose data. Keep revision 0007.")
    op.add_column("chat_messages", sa.Column("image_storage_key", sa.String(255)))
    op.add_column("chat_messages", sa.Column("image_content_type", sa.String(30)))
    connection.execute(sa.text(
        "UPDATE chat_messages SET image_storage_key = i.storage_key, image_content_type = i.content_type "
        "FROM chat_message_images i WHERE i.message_id = chat_messages.id"
    ))
    op.drop_constraint("ck_chat_messages_payload", "chat_messages", type_="check")
    op.create_check_constraint("ck_chat_messages_payload", "chat_messages",
        "(message_type = 'TEXT' AND content IS NOT NULL AND length(trim(content)) BETWEEN 1 AND 2000 "
        "AND image_storage_key IS NULL AND image_content_type IS NULL) OR "
        "(message_type = 'IMAGE' AND content IS NULL AND image_storage_key IS NOT NULL "
        "AND image_content_type IS NOT NULL AND image_content_type IN ('image/jpeg', 'image/png', 'image/webp'))")
    op.create_unique_constraint("chat_messages_image_storage_key_key", "chat_messages", ["image_storage_key"])
    op.drop_constraint("uq_chat_messages_client_message", "chat_messages", type_="unique")
    op.drop_column("chat_messages", "client_message_id")
    op.drop_column("chat_messages", "upload_fingerprint")
    op.drop_table("chat_message_images")
