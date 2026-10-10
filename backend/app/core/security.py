from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

password_context = CryptContext(schemes=["argon2"], deprecated="auto")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_secret(value: str) -> str:
    return password_context.hash(value)


def verify_secret(value: str, hashed_value: str) -> bool:
    return password_context.verify(value, hashed_value)


def _create_token(subject: UUID, token_type: str, expires_delta: timedelta, **extra: str) -> str:
    settings = get_settings()
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": utc_now(),
        "exp": utc_now() + expires_delta,
        **extra,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: UUID) -> str:
    return _create_token(
        user_id,
        "access",
        timedelta(minutes=get_settings().access_token_expire_minutes),
    )


def create_refresh_token(user_id: UUID, session_id: UUID) -> str:
    return _create_token(
        user_id,
        "refresh",
        timedelta(days=get_settings().refresh_token_expire_days),
        sid=str(session_id),
    )


def decode_token(token: str, expected_type: str) -> dict:
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type")
    return payload
