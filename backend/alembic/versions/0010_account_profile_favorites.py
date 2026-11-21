"""Add saved posts and enforce unique nicknames without removing existing data."""
from alembic import op
import sqlalchemy as sa

revision = "0010_account_profile_favorites"
down_revision = "0009_record_color_conflict"
branch_labels = None
depends_on = None


def upgrade() -> None:
    duplicate = op.get_bind().scalar(sa.text(
        "SELECT count(*) FROM (SELECT nickname FROM users GROUP BY nickname HAVING count(*) > 1) duplicates"
    ))
    if duplicate:
        raise RuntimeError("Duplicate nicknames exist. Resolve them explicitly before upgrading; no accounts were changed.")
    op.create_unique_constraint("uq_users_nickname", "users", ["nickname"])
    op.create_table(
        "favorite_posts",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("post_id", sa.Uuid(), sa.ForeignKey("posts.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    raise RuntimeError("Downgrade would remove saved posts and nickname protection; review explicitly before removal.")
