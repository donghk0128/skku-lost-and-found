"""Core authentication-flow tests that do not send a real email."""
import os
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

# These must exist before application modules read their settings.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough")

from app.auth.schemas import LoginRequest, SignUpRequest
from app.auth.repository import AuthRepository
from app.auth.service import AuthService
from app.core.database import Base, SessionLocal, engine
from app.core.errors import ApiError
from app.core.security import utc_now
from app.users.repository import UserRepository


class FakeEmailClient:
    """Captures the code so the authentication rules can be tested locally."""

    sent_to: str | None = None
    last_code: str | None = None

    def send_verification_code(self, recipient_email: str, code: str) -> None:
        self.sent_to = recipient_email
        self.last_code = code


@pytest.fixture()
def db() -> Session:

    if engine.dialect.name != "sqlite":
        raise RuntimeError("Auth tests must use SQLite; refusing to modify another database.")

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.mark.parametrize("email", ["student@not-skku.edu", "student@g.skku.edu", "student@skku.edu.example"])
def test_only_exact_skku_domain_can_receive_code(db: Session, email: str) -> None:
    service = AuthService(FakeEmailClient())

    with pytest.raises(ApiError) as error:
        service.send_verification_code(db, email)

    assert error.value.code == "invalid_university_email"
    assert "@skku.edu" in error.value.message


def test_signup_login_refresh_and_logout_flow(db: Session) -> None:
    email_client = FakeEmailClient()
    service = AuthService(email_client)
    email = "Student@SKku.EDU"

    service.send_verification_code(db, email)
    assert email_client.sent_to == "student@skku.edu"
    assert email_client.last_code is not None

    with pytest.raises(ApiError) as error:
        service.verify_email_code(db, email, "000000")
    assert error.value.code == "invalid_verification_code"

    service.verify_email_code(db, email, email_client.last_code)
    user, access_token, refresh_token = service.signup(
        db,
        SignUpRequest(email=email, nickname="테스터", password="safe-password-123"),
    )
    assert user.email == "student@skku.edu"
    assert access_token
    assert refresh_token
    assert UserRepository.get_by_email(db, user.email) is not None

    _, login_access_token, login_refresh_token = service.login(
        db,
        LoginRequest(email=email, password="safe-password-123"),
    )
    assert login_access_token
    assert service.refresh(db, login_refresh_token)

    service.logout(db, login_refresh_token)
    with pytest.raises(ApiError) as error:
        service.refresh(db, login_refresh_token)
    assert error.value.code == "invalid_refresh_token"


def test_expired_code_and_attempt_limit_are_enforced(db: Session) -> None:
    email_client = FakeEmailClient()
    service = AuthService(email_client)

    expired_email = "expired@skku.edu"
    service.send_verification_code(db, expired_email)
    expired = AuthRepository.get_latest_unverified_verification(db, expired_email)
    assert expired is not None
    expired.expires_at = utc_now() - timedelta(seconds=1)
    db.commit()
    with pytest.raises(ApiError) as error:
        service.verify_email_code(db, expired_email, email_client.last_code or "000000")
    assert error.value.code == "verification_expired"

    limited_email = "limited@skku.edu"
    service.send_verification_code(db, limited_email)
    for _ in range(5):
        with pytest.raises(ApiError) as error:
            service.verify_email_code(db, limited_email, "000000")
        assert error.value.code == "invalid_verification_code"
    with pytest.raises(ApiError) as error:
        service.verify_email_code(db, limited_email, "000000")
    assert error.value.code == "verification_attempts_exceeded"


def test_unverified_or_consumed_verification_cannot_create_another_account(db: Session) -> None:
    email_client = FakeEmailClient()
    service = AuthService(email_client)

    with pytest.raises(ApiError) as error:
        service.signup(
            db,
            SignUpRequest(email="unverified@skku.edu", nickname="미인증", password="safe-password-123"),
        )
    assert error.value.code == "email_not_verified"

    email = "consumed@skku.edu"
    service.send_verification_code(db, email)
    service.verify_email_code(db, email, email_client.last_code or "000000")
    user, _, _ = service.signup(
        db,
        SignUpRequest(email=email, nickname="소비됨", password="safe-password-123"),
    )
    assert AuthRepository.get_verified_verification(db, email, utc_now()) is None

    # Removing only the user simulates a future administrative cleanup; the consumed
    # verification itself must still never authorize another signup.
    db.delete(user)
    db.commit()
    with pytest.raises(ApiError) as error:
        service.signup(
            db,
            SignUpRequest(email=email, nickname="재사용", password="safe-password-123"),
        )
    assert error.value.code == "email_not_verified"
