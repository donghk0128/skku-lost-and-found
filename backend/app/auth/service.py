import re
import secrets
from hashlib import sha256
import unicodedata
from datetime import timedelta
from uuid import UUID, uuid4

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.repository import AuthRepository
from app.auth.schemas import LoginRequest, SignUpRequest
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_secret,
    utc_now,
    verify_secret,
)
from app.email.protocols import VerificationCodeSender
from app.email.service import EmailService
from app.users.model import EmailVerification, PasswordReset, User, UserSession
from app.users.repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)
MAX_VERIFICATION_ATTEMPTS = 5


def normalize_email(email: str) -> str:
    return unicodedata.normalize("NFKC", email).strip().lower()


def validate_university_email(email: str) -> str:
    normalized = normalize_email(email)
    parts = normalized.rsplit("@", 1)
    allowed_domain = get_settings().allowed_email_domain.lower()
    if len(parts) != 2 or not parts[0] or parts[1] != allowed_domain:
        # This generic response deliberately reveals no account information.
        raise ApiError(400, "invalid_university_email", f"성균관대학교 이메일(@{allowed_domain})만 사용할 수 있습니다.")
    return normalized


def _is_after_or_equal_now(value) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=utc_now().tzinfo)
    return value >= utc_now()


class AuthService:
    def __init__(self, email_sender: VerificationCodeSender | None = None):
        self.email_service = EmailService(email_sender)

    def send_verification_code(self, db: Session, email: str) -> None:
        email = validate_university_email(email)
        existing = AuthRepository.get_latest_unverified_verification(db, email)
        if existing is not None:
            created_at = existing.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=utc_now().tzinfo)
            elapsed_seconds = (utc_now() - created_at).total_seconds()
            if elapsed_seconds < get_settings().email_verification_resend_seconds:
                raise ApiError(429, "verification_resend_cooldown", "잠시 후 인증 코드를 다시 요청해 주세요.")

        code = f"{secrets.randbelow(1_000_000):06d}"
        verification = EmailVerification(
            email=email,
            code_hash=hash_secret(code),
            expires_at=utc_now() + timedelta(minutes=get_settings().email_verification_expire_minutes),
        )
        self.email_service.send_verification_code(email, code)
        AuthRepository.create_verification(db, verification)
        db.commit()

    def verify_email_code(self, db: Session, email: str, code: str) -> None:
        email = validate_university_email(email)
        verification = AuthRepository.get_latest_unverified_verification(db, email)
        if verification is None:
            raise ApiError(400, "verification_not_found", "사용할 수 있는 인증 요청이 없습니다.")
        if not _is_after_or_equal_now(verification.expires_at):
            raise ApiError(400, "verification_expired", "인증 코드가 만료되었습니다. 새 코드를 요청해 주세요.")
        if verification.attempt_count >= MAX_VERIFICATION_ATTEMPTS:
            raise ApiError(429, "verification_attempts_exceeded", "인증 시도 횟수를 초과했습니다. 새 코드를 요청해 주세요.")

        if not verify_secret(code, verification.code_hash):
            verification.attempt_count += 1
            db.commit()
            raise ApiError(400, "invalid_verification_code", "인증 코드가 올바르지 않습니다.")

        verification.verified_at = utc_now()
        db.commit()

    def send_password_reset_code(self, db: Session, email: str) -> None:
        email = validate_university_email(email)
        now = utc_now()
        reset = db.scalar(select(PasswordReset).where(PasswordReset.email == email).with_for_update())
        sent_at = reset.sent_at if reset is not None else None
        if sent_at is not None and sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=now.tzinfo)
        if sent_at is not None and (now - sent_at).total_seconds() < get_settings().email_verification_resend_seconds:
            raise ApiError(429, "verification_resend_cooldown", "잠시 후 인증 코드를 다시 요청해 주세요.")
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            return  # Keep the same response for registered and unregistered addresses.
        code = f"{secrets.randbelow(1_000_000):06d}"
        self.email_service.send_verification_code(email, code)
        if reset is None:
            reset = PasswordReset(email=email, code_hash="", expires_at=now, sent_at=now)
            db.add(reset)
        reset.code_hash = hash_secret(code)
        reset.token_hash = None
        reset.verified_at = None
        reset.attempt_count = 0
        reset.sent_at = now
        reset.expires_at = now + timedelta(minutes=get_settings().email_verification_expire_minutes)
        db.commit()

    def verify_password_reset_code(self, db: Session, email: str, code: str) -> str:
        email = validate_university_email(email)
        reset = db.scalar(select(PasswordReset).where(PasswordReset.email == email).with_for_update())
        if reset is None or reset.verified_at is not None or not _is_after_or_equal_now(reset.expires_at):
            raise ApiError(400, "verification_expired", "인증 코드가 없거나 만료되었습니다.")
        if reset.attempt_count >= MAX_VERIFICATION_ATTEMPTS:
            raise ApiError(429, "verification_attempts_exceeded", "인증 시도 횟수를 초과했습니다. 새 코드를 요청해 주세요.")
        if not verify_secret(code, reset.code_hash):
            reset.attempt_count += 1
            db.commit()
            raise ApiError(400, "invalid_verification_code", "인증 코드가 올바르지 않습니다.")
        token = secrets.token_urlsafe(32)
        reset.token_hash = sha256(token.encode()).hexdigest()
        reset.verified_at = utc_now()
        db.commit()
        return token

    def complete_password_reset(self, db: Session, email: str, token: str, password: str, confirmation: str) -> None:
        email = validate_university_email(email)
        if password != confirmation:
            raise ApiError(422, "password_mismatch", "비밀번호가 일치하지 않습니다.")
        if not (8 <= len(password) <= 20 and re.search("[A-Za-z]", password) and re.search("[0-9]", password)):
            raise ApiError(422, "invalid_password", "비밀번호는 영문과 숫자를 포함한 8~20자로 입력해 주세요.")
        user = db.scalar(select(User).where(User.email == email).with_for_update())
        reset = db.scalar(select(PasswordReset).where(PasswordReset.email == email).with_for_update())
        if user is None or reset is None or reset.verified_at is None or reset.token_hash != sha256(token.encode()).hexdigest() or not _is_after_or_equal_now(reset.expires_at):
            raise ApiError(400, "invalid_reset_token", "인증이 만료되었습니다. 다시 인증해 주세요.")
        user.password_hash = hash_secret(password)
        for session in db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))):
            session.revoked_at = utc_now()
        db.delete(reset)
        db.commit()

    def signup(self, db: Session, request: SignUpRequest) -> tuple[User, str, str]:
        email = validate_university_email(request.email)
        if UserRepository.get_by_email(db, email) is not None:
            raise ApiError(409, "email_already_registered", "이미 가입된 이메일입니다.")
        if UserRepository.get_by_nickname(db, request.nickname) is not None:
            raise ApiError(409, "nickname_already_registered", "이미 사용 중인 닉네임입니다.")

        verification = AuthRepository.get_verified_verification(db, email, utc_now())
        if verification is None:
            raise ApiError(400, "email_not_verified", "회원가입 전에 이메일 인증을 완료해 주세요.")

        user = User(
            email=email,
            password_hash=hash_secret(request.password),
            nickname=unicodedata.normalize("NFKC", request.nickname).strip(),
            email_verified_at=verification.verified_at,
        )
        verification.consumed_at = utc_now()
        try:
            AuthRepository.create_user(db, user)
            db.flush()  # Generate the UUID before it becomes part of the refresh-token claims.
            session, refresh_token = self._create_session(user.id)
            AuthRepository.create_session(db, session)
            db.commit()
        except IntegrityError as error:
            db.rollback()
            if UserRepository.get_by_email(db, email) is None and UserRepository.get_by_nickname(db, request.nickname) is not None:
                raise ApiError(409, "nickname_already_registered", "이미 사용 중인 닉네임입니다.") from error
            raise ApiError(409, "email_already_registered", "이미 가입된 이메일입니다.") from error
        db.refresh(user)
        return user, create_access_token(user.id), refresh_token

    def login(self, db: Session, request: LoginRequest) -> tuple[User, str, str]:
        email = normalize_email(request.email)
        user = db.scalar(select(User).where(User.email == email).with_for_update())
        if user is None or not verify_secret(request.password, user.password_hash):
            raise ApiError(401, "invalid_credentials", "이메일 또는 비밀번호가 올바르지 않습니다.")

        session, refresh_token = self._create_session(user.id)
        AuthRepository.create_session(db, session)
        db.commit()
        return user, create_access_token(user.id), refresh_token

    def refresh(self, db: Session, refresh_token: str) -> str:
        payload = self._decode_refresh_token(refresh_token)
        user = db.scalar(select(User).where(User.id == UUID(payload["sub"])).with_for_update())
        if user is None:
            raise ApiError(401, "invalid_refresh_token", "유효하지 않은 로그인 세션입니다.")
        session = AuthRepository.get_session(db, UUID(payload["sid"]))
        if session is None or session.user_id != user.id or session.revoked_at is not None or not _is_after_or_equal_now(session.expires_at):
            raise ApiError(401, "invalid_refresh_token", "로그인 세션이 만료되었거나 유효하지 않습니다.")
        if not verify_secret(refresh_token, session.refresh_token_hash):
            raise ApiError(401, "invalid_refresh_token", "로그인 세션이 만료되었거나 유효하지 않습니다.")
        return create_access_token(session.user_id)

    def logout(self, db: Session, refresh_token: str) -> None:
        payload = self._decode_refresh_token(refresh_token)
        session = AuthRepository.get_session(db, UUID(payload["sid"]))
        if session is not None and session.revoked_at is None and verify_secret(refresh_token, session.refresh_token_hash):
            session.revoked_at = utc_now()
            db.commit()

    @staticmethod
    def _create_session(user_id: UUID) -> tuple[UserSession, str]:
        session_id = uuid4()
        # The same signed token is returned only after its Argon2 hash is persisted.
        token = create_refresh_token(user_id, session_id)
        session = UserSession(
            id=session_id,
            user_id=user_id,
            refresh_token_hash=hash_secret(token),
            expires_at=utc_now() + timedelta(days=get_settings().refresh_token_expire_days),
        )
        return session, token

    @staticmethod
    def _decode_refresh_token(refresh_token: str) -> dict:
        try:
            payload = decode_token(refresh_token, "refresh")
            UUID(payload["sub"])
            UUID(payload["sid"])
            return payload
        except (jwt.PyJWTError, KeyError, ValueError) as error:
            raise ApiError(401, "invalid_refresh_token", "로그인 세션이 만료되었거나 유효하지 않습니다.") from error


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise ApiError(401, "authentication_required", "로그인이 필요합니다.")
    try:
        payload = decode_token(credentials.credentials, "access")
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as error:
        raise ApiError(401, "invalid_token", "유효하지 않은 인증 정보입니다.") from error
    user = db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
    if user is None:
        raise ApiError(401, "invalid_token", "유효하지 않은 인증 정보입니다.")
    return user
