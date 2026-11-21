from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import ApiError
from app.users.model import FavoritePost, User
from app.core.security import hash_secret, verify_secret
from app.posts.model import Post
from app.users.repository import UserRepository


class UserService:
    @staticmethod
    def update_nickname(db: Session, user: User, nickname: str) -> User:
        existing = UserRepository.get_by_nickname(db, nickname)
        if existing is not None and existing.id != user.id:
            raise ApiError(409, "nickname_already_registered", "이미 사용 중인 닉네임입니다.")
        user.nickname = nickname
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            raise ApiError(409, "nickname_already_registered", "이미 사용 중인 닉네임입니다.") from error
        return user

    @staticmethod
    def change_password(db: Session, user: User, current_password: str, password: str) -> None:
        # Serialize password checks against concurrent changes without ending the current login.
        user = db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
        if not verify_secret(current_password, user.password_hash):
            raise ApiError(400, "invalid_current_password", "현재 비밀번호가 올바르지 않습니다.")
        user.password_hash = hash_secret(password)
        db.commit()

    @staticmethod
    def post_list(db: Session, user: User, post_type: str | None, favorites: bool, limit: int, offset: int):
        query = select(Post).where(Post.deleted_at.is_(None))
        if favorites:
            query = query.join(FavoritePost, FavoritePost.post_id == Post.id).where(
                FavoritePost.user_id == user.id, Post.author_id != user.id,
            ).order_by(FavoritePost.created_at.desc(), Post.id.desc())
        else:
            query = query.where(Post.author_id == user.id).order_by(Post.created_at.desc(), Post.id.desc())
        if post_type is not None:
            query = query.where(Post.post_type == post_type)
        total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
        return list(db.scalars(query.limit(limit).offset(offset))), total

    @staticmethod
    def favorite_post(db: Session, user: User, post_id: UUID, saved: bool) -> None:
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        if saved:
            post = db.scalar(select(Post).where(Post.id == post_id, Post.deleted_at.is_(None)).with_for_update())
            if post is None:
                raise ApiError(404, "post_not_found", "게시글을 찾을 수 없습니다.")
            if post.author_id == user.id:
                raise ApiError(422, "own_post_favorite", "본인 게시글에는 관심 등록할 수 없습니다.")
        favorite = db.get(FavoritePost, (user.id, post_id))
        if saved and favorite is None:
            db.add(FavoritePost(user_id=user.id, post_id=post_id))
        elif not saved and favorite is not None:
            db.delete(favorite)
        db.commit()

    @staticmethod
    def get_me(db: Session, user_id: UUID) -> User:
        user = UserRepository.get_by_id(db, user_id)
        if user is None:
            raise ApiError(401, "invalid_token", "유효하지 않은 인증 정보입니다.")
        return user
