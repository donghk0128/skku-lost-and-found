"""Seed provisional categories for lost and found posts.

Revision ID: 0003_seed_post_categories
Revises: 0002_create_post_tables
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_seed_post_categories"
down_revision = "0002_create_post_tables"
branch_labels = None
depends_on = None


categories = sa.table(
    "categories",
    sa.column("id", sa.SmallInteger()),
    sa.column("code", sa.String(30)),
    sa.column("name", sa.String(50)),
)
posts = sa.table("posts", sa.column("category_id", sa.SmallInteger()))

SEED_CATEGORIES = (
    ("ELECTRONICS", "전자기기"),
    ("WALLET", "지갑"),
    ("ID_CARD", "신분증·카드"),
    ("BAG", "가방"),
    ("CLOTHING", "의류·잡화"),
    ("KEY", "열쇠"),
    ("BOOK_STATIONERY", "도서·문구"),
    ("OTHER", "기타"),
)
SEED_CODES = tuple(code for code, _ in SEED_CATEGORIES)


def upgrade() -> None:
    op.bulk_insert(
        categories,
        [{"code": code, "name": name} for code, name in SEED_CATEGORIES],
    )


def downgrade() -> None:
    connection = op.get_bind()
    referenced = connection.scalar(
        sa.select(sa.func.count())
        .select_from(posts.join(categories, posts.c.category_id == categories.c.id))
        .where(categories.c.code.in_(SEED_CODES))
    )
    if referenced:
        raise RuntimeError("게시글이 참조하는 카테고리는 제거할 수 없습니다.")
    connection.execute(categories.delete().where(categories.c.code.in_(SEED_CODES)))
