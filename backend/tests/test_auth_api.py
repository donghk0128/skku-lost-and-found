"""Verify the frontend auth contract and CORS with an isolated database."""
import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough")

from app.core.database import Base, get_db
from app.email.console_client import ConsoleEmailClient
from app.email.service import EmailService
from app.main import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def isolated_db() -> Generator[Session, None, None]:
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = isolated_db
    try:
        with TestClient(app) as api:
            yield api
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_signup_login_and_session_restore(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    codes: list[str] = []
    monkeypatch.setattr(ConsoleEmailClient, "send_verification_code", lambda self, email, code: codes.append(code))
    monkeypatch.setattr(EmailService, "_sender_for_configured_mode", staticmethod(lambda: ConsoleEmailClient()))
    email = "integration@skku.edu"
    credentials = {"email": email, "password": "integration-password-123"}
    assert client.post("/api/v1/auth/email/send-code", json={"email": email}).status_code == 202
    assert client.post("/api/v1/auth/signup", json={**credentials, "nickname": "통합테스터"}).status_code == 400
    assert client.post("/api/v1/auth/email/verify", json={"email": email, "code": codes[0]}).status_code == 200
    signup = client.post("/api/v1/auth/signup", json={**credentials, "nickname": "통합테스터"})
    assert signup.status_code == 201
    assert signup.json()["user"]["nickname"] == "통합테스터"
    wrong_password = client.post("/api/v1/auth/login", json={**credentials, "password": "wrong"})
    assert wrong_password.status_code == 401
    assert wrong_password.json()["error"]["message"]
    login = client.post("/api/v1/auth/login", json=credentials)
    assert login.status_code == 200
    session = login.json()
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {session['access_token']}"})
    assert me.status_code == 200
    assert me.json()["id"] == signup.json()["user"]["id"]
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert refreshed.status_code == 200
    assert client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"}).status_code == 200


def test_password_reset_requires_own_email_code_and_signup_password_rules(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    codes: list[str] = []
    monkeypatch.setattr(ConsoleEmailClient, "send_verification_code", lambda self, email, code: codes.append(code))
    monkeypatch.setattr(EmailService, "_sender_for_configured_mode", staticmethod(lambda: ConsoleEmailClient()))
    email = "recovery@skku.edu"
    client.post("/api/v1/auth/email/send-code", json={"email": email})
    client.post("/api/v1/auth/email/verify", json={"email": email, "code": codes[-1]})
    signup = client.post("/api/v1/auth/signup", json={"email": email, "nickname": "복구테스터", "password": "Oldpassword1"})
    assert signup.status_code == 201
    assert client.post("/api/v1/auth/password-reset/send-code", json={"email": email}).status_code == 202
    assert client.post("/api/v1/auth/password-reset/verify", json={"email": email, "code": "000000"}).status_code == 400
    verified = client.post("/api/v1/auth/password-reset/verify", json={"email": email, "code": codes[-1]})
    assert verified.status_code == 200
    payload = {"email": email, "reset_token": verified.json()["reset_token"], "password": "abcdefgh", "password_confirmation": "abcdefgh"}
    assert client.post("/api/v1/auth/password-reset/complete", json=payload).status_code == 422
    payload["password"] = payload["password_confirmation"] = "Newpassword1"
    assert client.post("/api/v1/auth/password-reset/complete", json=payload).status_code == 200
    assert client.post("/api/v1/auth/password-reset/complete", json=payload).status_code == 400
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "Oldpassword1"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": email, "password": "Newpassword1"}).status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": signup.json()["refresh_token"]}).status_code == 401


@pytest.mark.parametrize("origin", ["http://localhost:8081", "http://127.0.0.1:8081"])
def test_auth_browser_preflight(client: TestClient, origin: str) -> None:
    response = client.options("/api/v1/auth/login", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,authorization",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    rejected = client.options("/api/v1/auth/login", headers={
        "Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST",
    })
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers
