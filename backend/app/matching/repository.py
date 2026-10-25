"""Database queries for recommendation candidates."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.posts.model import Post


class MatchingRepository:
    @staticmethod
    def list_candidates(db: Session, source: Post) -> list[Post]:
        opposite_type = "FOUND" if source.post_type == "LOST" else "LOST"
        statement = select(Post).where(
            Post.post_type == opposite_type,
            Post.status == "OPEN",
            Post.deleted_at.is_(None),
        )
        return list(db.scalars(statement).all())
