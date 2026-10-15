"""Database reads and writes for posts."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.posts.model import Post


class PostRepository:
    @staticmethod
    def create(db: Session, post: Post) -> Post:
        db.add(post)
        return post

    @staticmethod
    def get_visible_by_id(db: Session, post_id: UUID) -> Post | None:
        statement = select(Post).where(Post.id == post_id, Post.deleted_at.is_(None))
        return db.scalar(statement)
