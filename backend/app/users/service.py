from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.users.model import User
from app.users.repository import UserRepository


class UserService:
    @staticmethod
    def get_me(db: Session, user_id: UUID) -> User:
        user = UserRepository.get_by_id(db, user_id)
        if user is None:
            raise ApiError(401, "invalid_token", "유효하지 않은 인증 정보입니다.")
        return user
