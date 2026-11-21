"""Profile editing and saved posts use isolated SQLite; no real accounts or email."""
from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from test_posts_api import api_client, create_author
from app.core.security import create_access_token, hash_secret, utc_now
from app.email.service import EmailService
from app.users.model import FavoritePost, User

ROOT = "/api/v1/users/me"


@pytest.fixture()
def account(api_client):
    client, engine = api_client
    owner = create_author(engine, "account@skku.edu")
    other = create_author(engine, "other@skku.edu")
    with Session(engine) as db:
        db.get(User, owner).password_hash = hash_secret("old-password-123")
        db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(owner)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other)}"}
    return client, engine, owner, other, headers, other_headers


def create_post(client, headers, kind="LOST", title="테스트 게시글"):
    response = client.post("/api/v1/posts", headers=headers, json={"post_type": kind, "title": title, "description": "분실물"})
    assert response.status_code == 201
    return response.json()["id"]


def test_nickname_change_rejects_duplicates_and_preserves_own_name(account):
    client, engine, _, _, headers, other_headers = account
    assert client.patch(ROOT, headers=headers, json={"nickname": "  Ａlice  "}).json()["nickname"] == "Alice"
    assert client.patch(ROOT, headers=headers, json={"nickname": "Alice"}).status_code == 200
    duplicate = client.patch(ROOT, headers=other_headers, json={"nickname": "Ａlice"})
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "nickname_already_registered"
    for payload in ({"nickname": "  "}, {"nickname": "x"}, {"nickname": "new", "email": "hack@skku.edu"}):
        assert client.patch(ROOT, headers=headers, json=payload).status_code == 422
    assert client.patch(ROOT, json={"nickname": "new"}).status_code == 401
    # Even direct DB writes cannot bypass the unique constraint.
    with Session(engine) as db:
        db.add(User(email="third@skku.edu", nickname="Alice", password_hash="test", email_verified_at=utc_now()))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_signup_uses_the_same_nickname_protection(account, monkeypatch):
    client, _, _, _, headers, _ = account
    client.patch(ROOT, headers=headers, json={"nickname": "Unique"})
    codes = []
    monkeypatch.setattr(EmailService, "send_verification_code", lambda self, email, code: codes.append(code))
    email = "signup-new@skku.edu"
    assert client.post("/api/v1/auth/email/send-code", json={"email": email}).status_code == 202
    assert client.post("/api/v1/auth/email/verify", json={"email": email, "code": codes[-1]}).status_code == 200
    signup = {"email": email, "nickname": " Ｕnique ", "password": "new-password-123"}
    assert client.post("/api/v1/auth/signup", json=signup).status_code == 409
    signup["nickname"] = "Another"
    assert client.post("/api/v1/auth/signup", json=signup).status_code == 201


def test_password_change_checks_current_and_keeps_login(account):
    client, _, _, _, _, _ = account
    credentials = {"email": "account@skku.edu", "password": "old-password-123"}
    session = client.post("/api/v1/auth/login", json=credentials).json()
    headers = {"Authorization": "Bearer " + session["access_token"]}
    payload = {"current_password": "wrong", "password": "changed-password-123", "password_confirmation": "changed-password-123"}
    assert client.post(ROOT + "/password", headers=headers, json=payload).status_code == 400
    payload["current_password"] = "old-password-123"
    payload["password_confirmation"] = "mismatch"
    assert client.post(ROOT + "/password", headers=headers, json=payload).status_code == 422
    payload["password_confirmation"] = payload["password"]
    assert client.post(ROOT + "/password", json=payload).status_code == 401
    assert client.post(ROOT + "/password", headers=headers, json=payload).status_code == 200
    assert client.get(ROOT, headers=headers).status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}).status_code == 200
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 401
    credentials["password"] = payload["password"]
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 200


def test_saved_posts_are_idempotent_private_and_exclude_self_deleted(account):
    client, engine, owner, _, headers, other_headers = account
    own = create_post(client, headers)
    lost = create_post(client, other_headers)
    found = create_post(client, other_headers, "FOUND")
    assert client.post(ROOT + "/favorites/" + own, headers=headers).status_code == 422
    assert client.post(ROOT + "/favorites/" + lost).status_code == 401
    for pid in (lost, lost, found):
        assert client.post(ROOT + "/favorites/" + pid, headers=headers).status_code == 204
    assert client.get(ROOT + "/favorites/" + lost, headers=headers).json()["saved"]
    assert client.get(ROOT + "/favorites/" + lost, headers=other_headers).json()["saved"] is False
    first = client.get(ROOT + "/favorites?limit=1", headers=headers).json()
    second = client.get(ROOT + "/favorites?limit=1&offset=1", headers=headers).json()
    assert first["total"] == second["total"] == 2
    assert {first["items"][0]["id"], second["items"][0]["id"]} == {lost, found}
    assert client.get(ROOT + "/favorites", headers=other_headers).json()["items"] == []
    assert client.delete("/api/v1/posts/" + lost, headers=other_headers).status_code == 204
    assert client.get(ROOT + "/favorites/" + lost, headers=headers).json()["saved"] is False
    assert client.get(ROOT + "/favorites", headers=headers).json()["total"] == 1
    assert client.post(ROOT + "/favorites/" + lost, headers=headers).status_code == 404
    for _ in range(2):
        assert client.delete(ROOT + "/favorites/" + found, headers=headers).status_code == 204
    with Session(engine) as db:
        assert len(list(db.scalars(select(FavoritePost).where(FavoritePost.user_id == owner)))) == 1


def test_my_posts_include_completed_and_respect_type_owner_and_pagination(account):
    client, _, _, _, headers, other_headers = account
    lost = [create_post(client, headers, title=f"lost-{i}") for i in range(3)]
    found = create_post(client, headers, "FOUND")
    create_post(client, other_headers)
    assert client.patch("/api/v1/posts/" + lost[1] + "/status", headers=headers, json={"status": "COMPLETED"}).status_code == 200
    assert client.delete("/api/v1/posts/" + lost[0], headers=headers).status_code == 204
    first = client.get(ROOT + "/posts?post_type=LOST&limit=1", headers=headers).json()
    second = client.get(ROOT + "/posts?post_type=LOST&limit=1&offset=1", headers=headers).json()
    assert first["total"] == second["total"] == 2
    assert {first["items"][0]["id"], second["items"][0]["id"]} == set(lost[1:])
    assert client.get(ROOT + "/posts?post_type=FOUND", headers=headers).json()["items"][0]["id"] == found
    assert client.get(ROOT + "/posts", headers=headers).json()["total"] == 3
    assert client.get(ROOT + "/posts?post_type=FOUND", headers=other_headers).json()["total"] == 0
    assert client.get(ROOT + "/posts?post_type=LOST").status_code == 401
    # The candidate-selection API remains restricted to open posts.
    assert client.get("/api/v1/posts/mine?post_type=LOST", headers=headers).json()["total"] == 1


def test_withdrawal_requires_proof_and_keywords_remain_unimplemented(account):
    client, _, _, _, headers, _ = account
    assert client.delete(ROOT, headers=headers).status_code == 422
    assert client.post(ROOT + "/withdrawal/send-code", headers=headers).status_code == 422
    assert client.get(ROOT + "/keywords", headers=headers).status_code == 404
