"""Database reads and writes for posts."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.posts.model import Category, Post, PostImage


class PostRepository:
    SEARCH_WHITESPACE = (" ", "\t", "\n", "\r", "\u00a0")

    @staticmethod
    def add_image(db: Session, image: PostImage) -> None:
        db.add(image)

    @staticmethod
    def list_images(db: Session, post_id: UUID) -> list[PostImage]:
        return list(
            db.scalars(
                select(PostImage)
                .where(PostImage.post_id == post_id)
                .order_by(PostImage.position, PostImage.created_at, PostImage.id)
            ).all()
        )

    @staticmethod
    def get_image(db: Session, post_id: UUID, image_id: UUID) -> PostImage | None:
        return db.scalar(
            select(PostImage).where(PostImage.post_id == post_id, PostImage.id == image_id)
        )

    @staticmethod
    def list_categories(db: Session) -> list[Category]:
        return list(db.scalars(select(Category).order_by(Category.id)).all())

    @staticmethod
    def get_category_by_id(db: Session, category_id: int) -> Category | None:
        return db.get(Category, category_id)

    @staticmethod
    def get_category_by_code(db: Session, code: str) -> Category | None:
        return db.scalar(select(Category).where(Category.code == code))

    @staticmethod
    def create(db: Session, post: Post) -> Post:
        db.add(post)
        return post

    @staticmethod
    def update_details(post: Post, changes: dict[str, object]) -> None:
        for field, value in changes.items():
            setattr(post, field, value)

    @staticmethod
    def mark_deleted(post: Post, deleted_at: datetime) -> None:
        post.deleted_at = deleted_at

    @staticmethod
    def mark_completed(post: Post) -> None:
        post.status = "COMPLETED"

    @staticmethod
    def get_visible_by_id(db: Session, post_id: UUID) -> Post | None:
        statement = select(Post).where(Post.id == post_id, Post.deleted_at.is_(None))
        return db.scalar(statement)

    @staticmethod
    def list_visible(
        db: Session,
        post_type: str | None,
        category_id: int | None,
        post_status: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Post], int]:
        filters = [Post.deleted_at.is_(None)]
        if post_type is not None:
            filters.append(Post.post_type == post_type)
        if category_id is not None:
            filters.append(Post.category_id == category_id)
        if post_status is not None:
            filters.append(Post.status == post_status)
        if search is not None:
            search_fields = []
            for field in (Post.title, Post.description, Post.item_name):
                compact = func.coalesce(field, "")
                for whitespace in PostRepository.SEARCH_WHITESPACE:
                    compact = func.replace(compact, whitespace, "")
                search_fields.append(func.lower(compact))
            for term in search.split():
                compact_term = term.lower()
                filters.append(or_(*(field.contains(compact_term, autoescape=True) for field in search_fields)))

        total = db.scalar(select(func.count()).select_from(Post).where(*filters)) or 0
        statement = (
            select(Post)
            .where(*filters)
            .order_by(Post.created_at.desc(), Post.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(db.scalars(statement).all()), total
