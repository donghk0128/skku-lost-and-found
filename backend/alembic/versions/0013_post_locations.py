"""Store ordered post locations and backfill the legacy representative.

Revision ID: 0013_post_locations
Revises: 0012_password_reset
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_post_locations"
down_revision = "0012_password_reset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    locations = op.create_table(
        "post_locations",
        sa.Column("post_id", sa.Uuid(), sa.ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("position", sa.SmallInteger(), primary_key=True),
        sa.Column("location_text", sa.String(255)),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.CheckConstraint("position BETWEEN 0 AND 19", name="ck_post_locations_position"),
        sa.CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_post_locations_coordinates_together",
        ),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_post_locations_latitude_range"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_post_locations_longitude_range"),
        sa.CheckConstraint(
            "location_text IS NULL OR length(trim(location_text)) > 0", name="ck_post_locations_text_not_blank",
        ),
        sa.CheckConstraint(
            "location_text IS NOT NULL OR latitude IS NOT NULL", name="ck_post_locations_not_empty",
        ),
    )
    posts = sa.table(
        "posts", sa.column("id", sa.Uuid()), sa.column("location_text", sa.String(255)),
        sa.column("latitude", sa.Numeric(9, 6)), sa.column("longitude", sa.Numeric(9, 6)),
    )
    # Include completed and soft-deleted posts; blank legacy labels become NULL.
    label = sa.case((sa.func.length(sa.func.trim(posts.c.location_text)) > 0, posts.c.location_text), else_=None)
    op.execute(locations.insert().from_select(
        ["post_id", "position", "location_text", "latitude", "longitude"],
        sa.select(posts.c.id, sa.literal(0), label, posts.c.latitude, posts.c.longitude).where(
            sa.or_(label.is_not(None), posts.c.latitude.is_not(None)),
        ),
    ))


def downgrade() -> None:
    # Existing scalar columns retain position 0, but cannot retain extra rows.
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM post_locations WHERE position > 0")):
        raise RuntimeError("Cannot downgrade: multiple post locations would lose data. Keep revision 0013.")
    op.drop_table("post_locations")
