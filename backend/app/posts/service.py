"""Business rules for creating and reading posts."""

from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.posts.model import Post
from app.posts.repository import PostRepository
from app.posts.schemas import PostCreateRequest
from app.users.model import User


class PostService:
    @staticmethod
    def create(db: Session, request: PostCreateRequest, author: User) -> Post:
        post = Post(
            author_id=author.id,
            post_type=request.post_type,
            title=request.title,
            description=request.description,
        )
        PostRepository.create(db, post)
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise
        db.refresh(post)
        return post

    @staticmethod
    def get_visible_by_id(db: Session, post_id: UUID) -> Post:
        post = PostRepository.get_visible_by_id(db, post_id)
        if post is None:
            raise ApiError(404, "post_not_found", "게시글을 찾을 수 없습니다.")
        return post
