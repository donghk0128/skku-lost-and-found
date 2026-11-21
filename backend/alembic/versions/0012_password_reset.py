"""Store independent, one-time password recovery challenges.

Revision ID: 0012_password_reset
Revises: 0011_account_withdrawal
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_password_reset"
down_revision = "0011_account_withdrawal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_resets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("password_resets")
