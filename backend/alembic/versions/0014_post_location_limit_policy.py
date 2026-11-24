"""Keep the adjustable location count policy in the API instead of a DB bound.

Revision ID: 0014_post_location_limit_policy
Revises: 0013_post_locations
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_post_location_limit_policy"
down_revision = "0013_post_locations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("post_locations") as batch:
        batch.drop_constraint("ck_post_locations_position", type_="check")
        batch.create_check_constraint("ck_post_locations_position", "position >= 0")


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM post_locations WHERE position > 19")):
        raise RuntimeError("Cannot downgrade: existing locations exceed the old 20-location limit.")
    with op.batch_alter_table("post_locations") as batch:
        batch.drop_constraint("ck_post_locations_position", type_="check")
        batch.create_check_constraint("ck_post_locations_position", "position BETWEEN 0 AND 19")
