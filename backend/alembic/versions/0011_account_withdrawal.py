"""Allow hard account deletion while retaining the other chat member's history."""
from alembic import op
import sqlalchemy as sa

revision = "0011_account_withdrawal"
down_revision = "0010_account_profile_favorites"
branch_labels = None
depends_on = None


def replace_fk(table: str, column: str, target: str, ondelete: str) -> None:
    matches = [fk for fk in sa.inspect(op.get_bind()).get_foreign_keys(table) if fk["constrained_columns"] == [column]]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one foreign key for {table}.{column}")
    op.drop_constraint(matches[0]["name"], table, type_="foreignkey")
    op.create_foreign_key(f"fk_{table}_{column}_{target}", table, target, [column], ["id"], ondelete=ondelete)


def upgrade() -> None:
    for column, target in (("post_id", "posts"), ("owner_id", "users"), ("requester_id", "users")):
        op.alter_column("chat_rooms", column, existing_type=sa.Uuid(), nullable=True)
        replace_fk("chat_rooms", column, target, "SET NULL")
    op.alter_column("chat_messages", "sender_id", existing_type=sa.Uuid(), nullable=True)
    replace_fk("chat_messages", "sender_id", "users", "SET NULL")
    replace_fk("chat_room_members", "user_id", "users", "CASCADE")
    op.create_check_constraint("ck_chat_rooms_active_references", "chat_rooms",
        "status = 'CLOSED' OR (post_id IS NOT NULL AND owner_id IS NOT NULL AND requester_id IS NOT NULL)")
    op.create_table(
        "withdrawal_challenges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("credential_digest", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("code_hash", sa.Text()),
        sa.Column("code_sent_at", sa.DateTime(timezone=True)),
        sa.Column("code_expires_at", sa.DateTime(timezone=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    raise RuntimeError("Withdrawn chat references cannot be reconstructed. Destructive downgrade requires explicit review.")
