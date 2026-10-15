"""Database reads and writes for posts."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.posts.model import Category, Post, PostImage


class PostRepository:
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
    def get_visible_by_id(db: Session, post_id: UUID) -> Post | None:
        statement = select(Post).where(Post.id == post_id, Post.deleted_at.is_(None))
        return db.scalar(statement)

    @staticmethod
    def list_visible(
        db: Session, post_type: str | None, category_id: int | None, limit: int, offset: int
    ) -> tuple[list[Post], int]:
        filters = [Post.deleted_at.is_(None)]
        if post_type is not None:
            filters.append(Post.post_type == post_type)
        if category_id is not None:
            filters.append(Post.category_id == category_id)

        total = db.scalar(select(func.count()).select_from(Post).where(*filters)) or 0
        statement = (
            select(Post)
            .where(*filters)
            .order_by(Post.created_at.desc(), Post.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(db.scalars(statement).all()), total
