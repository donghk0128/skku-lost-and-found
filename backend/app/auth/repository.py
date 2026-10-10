from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.users.model import EmailVerification, User, UserSession


class AuthRepository:
    @staticmethod
    def get_latest_unverified_verification(db: Session, email: str) -> EmailVerification | None:
        statement = (
            select(EmailVerification)
            .where(
                EmailVerification.email == email,
                EmailVerification.verified_at.is_(None),
                EmailVerification.consumed_at.is_(None),
            )
            .order_by(EmailVerification.created_at.desc())
            .limit(1)
        )
        return db.scalar(statement)

    @staticmethod
    def get_verified_verification(db: Session, email: str, now: datetime) -> EmailVerification | None:
        statement = (
            select(EmailVerification)
            .where(
                EmailVerification.email == email,
                EmailVerification.verified_at.is_not(None),
                EmailVerification.consumed_at.is_(None),
                EmailVerification.expires_at >= now,
            )
            .order_by(EmailVerification.verified_at.desc())
            .limit(1)
        )
        return db.scalar(statement)

    @staticmethod
    def create_verification(db: Session, verification: EmailVerification) -> EmailVerification:
        db.add(verification)
        return verification

    @staticmethod
    def create_user(db: Session, user: User) -> User:
        db.add(user)
        return user

    @staticmethod
    def create_session(db: Session, session: UserSession) -> UserSession:
        db.add(session)
        return session

    @staticmethod
    def get_session(db: Session, session_id: UUID) -> UserSession | None:
        return db.get(UserSession, session_id)
