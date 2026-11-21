"""Real deletion and retained peer history; all data and email are isolated."""
from datetime import timedelta
import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from test_account_api import account, create_post
from test_posts_api import api_client as sqlite_api_client
from app.core.database import Base, get_db
from app.main import app
from app.core.errors import ApiError
from app.core.security import hash_secret, utc_now
from app.email.service import EmailService
from app.matching.model import PostEmbedding, RecommendationItem, RecommendationRun
from app.posts.model import Post, PostImage
from app.posts.storage import LocalPostImageStorage
from app.chat.model import ChatMessage, ChatMessageImage, ChatRoom, ChatRoomMember
from app.users.model import EmailVerification, FavoritePost, User, UserSession, WithdrawalChallenge
from app.users.withdrawal import WithdrawalService

ROOT = "/api/v1/users/me"
FLOW = ROOT + "/withdrawal"
PNG = b"\x89PNG\r\n\x1a\nwithdrawal-test"


@pytest.fixture()
def api_client(request):
    url = os.getenv("TEST_WITHDRAWAL_DATABASE_URL")
    if not url:
        yield request.getfixturevalue("sqlite_api_client")
        return
    parsed = make_url(url)
    assert parsed.get_backend_name() == "postgresql" and parsed.database.endswith("_test"), "Use a disposable *_test database"
    engine = create_engine(url, connect_args={"options": "-c lock_timeout=5000 -c statement_timeout=15000 -c search_path=public,extensions"})
    def clear_test_rows():
        with engine.begin() as c:
            for table in reversed(Base.metadata.sorted_tables):
                c.execute(table.delete())
    clear_test_rows()
    def sessions():
        with Session(engine) as db:
            yield db
    original = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = sessions
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        if original is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = original
        clear_test_rows()
        engine.dispose()


@pytest.fixture()
def withdrawal(account, monkeypatch, tmp_path):
    client, engine, uid, peer, headers, peer_headers = account
    monkeypatch.setattr("app.posts.service.sync_post_embedding", lambda db, post: None)
    if engine.dialect.name == "sqlite":
        with engine.connect() as c:
            c.exec_driver_sql("PRAGMA foreign_keys=ON")
    posts = LocalPostImageStorage(tmp_path / "posts")
    chats = LocalPostImageStorage(tmp_path / "chats")
    monkeypatch.setattr("app.posts.service.get_post_image_storage", lambda: posts)
    monkeypatch.setattr("app.users.withdrawal.get_post_image_storage", lambda: posts)
    monkeypatch.setattr("app.chat.service.get_chat_image_storage", lambda: chats)
    monkeypatch.setattr("app.chat.router.get_chat_image_storage", lambda: chats)
    monkeypatch.setattr("app.users.withdrawal.get_chat_image_storage", lambda: chats)
    codes = []
    counter = iter(range(100001, 200000))
    monkeypatch.setattr("app.users.withdrawal.secrets.randbelow", lambda _: next(counter))
    monkeypatch.setattr(EmailService, "send_verification_code", lambda self, email, code: codes.append((email, code)))
    return dict(client=client, engine=engine, uid=uid, peer=peer, headers=headers, peer_headers=peer_headers,
                posts=posts, chats=chats, codes=codes)


def start(ctx, headers=None, password="old-password-123"):
    response = ctx["client"].post(FLOW + "/password", headers=headers or ctx["headers"], json={"current_password": password})
    assert response.status_code == 200, response.text
    return response.json()["withdrawal_token"]


def verify(ctx, token, headers=None):
    headers = headers or ctx["headers"]
    response = ctx["client"].post(FLOW + "/send-code", headers=headers, json={"withdrawal_token": token})
    assert response.status_code == 202, response.text
    response = ctx["client"].post(FLOW + "/verify-email", headers=headers, json={"withdrawal_token": token, "code": ctx["codes"][-1][1]})
    assert response.status_code == 200, response.text


def remove(ctx, token, headers=None, confirmed=True):
    return ctx["client"].request("DELETE", ROOT, headers=headers or ctx["headers"], json={"withdrawal_token": token, "confirmed": confirmed})


def upload_post(ctx, pid, headers=None):
    response = ctx["client"].post(f"/api/v1/posts/{pid}/images", headers=headers or ctx["headers"], files={"file": ("photo.png", PNG, "image/png")})
    assert response.status_code == 201, response.text
    with Session(ctx["engine"]) as db:
        return db.scalar(select(PostImage.storage_key).where(PostImage.id == UUID(response.json()["id"])))


def test_password_then_email_are_required_and_proof_is_private(withdrawal):
    c = withdrawal
    client, headers = c["client"], c["headers"]
    assert client.post(FLOW + "/password", json={"current_password": "old-password-123"}).status_code == 401
    assert client.post(FLOW + "/password", headers=headers, json={"current_password": "wrong"}).status_code == 400
    fake = "x" * 43
    assert client.post(FLOW + "/send-code", headers=headers, json={"withdrawal_token": fake}).status_code == 400
    token = start(c)
    assert remove(c, token).status_code == 400
    assert remove(c, token, c["peer_headers"]).status_code == 400
    assert client.post(FLOW + "/send-code", headers=headers, json={"withdrawal_token": token, "email": "attacker@skku.edu"}).status_code == 422
    verify(c, token)
    assert c["codes"][-1][0] == "account@skku.edu"
    assert client.post("/api/v1/auth/email/verify", json={"email": "account@skku.edu", "code": c["codes"][-1][1]}).status_code == 400
    assert remove(c, token, confirmed=False).status_code == 422
    with Session(c["engine"]) as db:
        proof = db.scalar(select(WithdrawalChallenge).where(WithdrawalChallenge.user_id == c["uid"]))
        assert proof.token_hash != token and proof.code_hash != c["codes"][-1][1]
        assert proof.verified_at and db.get(User, c["uid"]) is not None


def test_code_attempts_resend_expiry_and_password_change_invalidate_proof(withdrawal):
    c = withdrawal
    client, headers = c["client"], c["headers"]
    token = start(c)
    assert client.post(FLOW + "/send-code", headers=headers, json={"withdrawal_token": token}).status_code == 202
    old_code = c["codes"][-1][1]
    assert client.post(FLOW + "/send-code", headers=headers, json={"withdrawal_token": token}).status_code == 429
    for _ in range(5):
        assert client.post(FLOW + "/verify-email", headers=headers, json={"withdrawal_token": token, "code": "999999"}).status_code == 400
    assert client.post(FLOW + "/verify-email", headers=headers, json={"withdrawal_token": token, "code": old_code}).status_code == 429
    with Session(c["engine"]) as db:
        db.scalar(select(WithdrawalChallenge)).code_sent_at = utc_now() - timedelta(minutes=2)
        db.commit()
    assert client.post(FLOW + "/send-code", headers=headers, json={"withdrawal_token": token}).status_code == 202
    assert client.post(FLOW + "/verify-email", headers=headers, json={"withdrawal_token": token, "code": old_code}).status_code == 400
    assert client.post(FLOW + "/verify-email", headers=headers, json={"withdrawal_token": token, "code": c["codes"][-1][1]}).status_code == 200
    with Session(c["engine"]) as db:
        db.scalar(select(WithdrawalChallenge)).code_expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    assert remove(c, token).status_code == 400
    fresh = start(c)
    assert remove(c, token).status_code == 400
    verify(c, fresh)
    assert client.post(ROOT + "/password", headers=headers, json={"current_password": "old-password-123", "password": "changed-password-123", "password_confirmation": "changed-password-123"}).status_code == 200
    assert remove(c, fresh).status_code == 400
    with Session(c["engine"]) as db:
        assert db.get(User, c["uid"]) is not None


def seed_history(c):
    client, headers, peer_headers = c["client"], c["headers"], c["peer_headers"]
    posts = [create_post(client, headers, title=f"owned-{i}") for i in range(4)]
    peer_post = create_post(client, peer_headers, "FOUND", "peer-owned")
    keys = [upload_post(c, pid) for pid in posts]
    peer_key = upload_post(c, peer_post, peer_headers)
    rooms = [client.post("/api/v1/chat/rooms", headers=peer_headers, json={"post_id": pid}).json()["id"] for pid in posts[:3]]
    peer_room = client.post("/api/v1/chat/rooms", headers=headers, json={"post_id": peer_post}).json()["id"]
    path = "/api/v1/chat/rooms/" + rooms[0]
    client.post(path + "/messages", headers=headers, json={"content": "old conversation"})
    client.post(path + "/messages", headers=peer_headers, json={"content": "peer reply"})
    image = client.post(path + "/images", headers=headers, files={"file": ("chat.png", PNG, "image/png")})
    assert image.status_code == 201
    client.post("/api/v1/chat/rooms/" + rooms[1] + "/close", headers=peer_headers, json={"reason": "RETURNED"})
    client.post("/api/v1/chat/rooms/" + rooms[2] + "/close", headers=peer_headers, json={"reason": "GENERAL"})
    assert client.delete("/api/v1/posts/" + posts[3], headers=headers).status_code == 204
    client.post(ROOT + "/favorites/" + posts[0], headers=peer_headers)
    client.post(ROOT + "/favorites/" + peer_post, headers=headers)
    with Session(c["engine"]) as db:
        db.add(EmailVerification(email="account@skku.edu", code_hash="old", expires_at=utc_now() + timedelta(minutes=5)))
        db.add(PostEmbedding(post_id=UUID(posts[0]), model="test", content_hash="x" * 64, embedding=[0.0] * 768))
        run = RecommendationRun(id=uuid4(), source_post_id=UUID(peer_post), algorithm_version="test", fingerprint="f" * 64, filters={}, candidate_count=1)
        db.add(run)
        db.flush()
        db.add(RecommendationItem(run_id=run.id, candidate_post_id=UUID(posts[0]), rank=1, final_score=1,
            rule_score=1, text_score=1, category_score=1, time_score=1, location_score=1, reasons=[]))
        db.commit()
    return posts, keys, peer_post, peer_key, rooms, peer_room, image.json()["image_url"]


def test_hard_deletion_retains_peer_history_and_rejoin_has_no_old_access(withdrawal):
    c = withdrawal
    client, headers, peer_headers = c["client"], c["headers"], c["peer_headers"]
    session = client.post("/api/v1/auth/login", json={"email": "account@skku.edu", "password": "old-password-123"}).json()
    data = seed_history(c)
    posts, keys, peer_post, peer_key, rooms, peer_room, chat_image_url = data
    token = start(c)
    verify(c, token)
    assert remove(c, token).status_code == 204
    assert remove(c, token).status_code == 401
    assert client.get(ROOT, headers=headers).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}).status_code == 401
    for pid in posts:
        assert client.get("/api/v1/posts/" + pid).status_code == 404
    for key in keys:
        assert not c["posts"]._path(key).exists()
    assert c["posts"].download(peer_key) == PNG
    for rid, reason in zip(rooms, ["GENERAL", "RETURNED", "GENERAL"]):
        room = client.get("/api/v1/chat/rooms/" + rid, headers=peer_headers).json()
        assert room["status"] == "CLOSED" and room["close_reason"] == reason
        assert room["other_nickname"] == "탈퇴한 사용자" and room["other_withdrawn"]
        assert room["post_id"] is None and room["post_deleted"] and room["post_title"] == "삭제된 게시물입니다."
    peer_detail = client.get("/api/v1/chat/rooms/" + peer_room, headers=peer_headers).json()
    assert peer_detail["other_withdrawn"] and peer_detail["close_reason"] == "GENERAL" and not peer_detail["post_deleted"]
    path = "/api/v1/chat/rooms/" + rooms[0]
    messages = client.get(path + "/messages", headers=peer_headers).json()["items"]
    assert len(messages) == 3 and messages[0]["sender_id"] is None
    assert messages[1]["sender_id"] == str(c["peer"])
    assert client.get(chat_image_url, headers=peer_headers).content == PNG
    assert client.post(path + "/messages", headers=peer_headers, json={"content": "no"}).status_code == 409
    assert client.patch(path + "/read", headers=peer_headers, json={"sequence": 3}).status_code == 200
    assert client.patch(path + "/visibility", headers=peer_headers, json={"is_hidden": True}).status_code == 200
    assert client.patch(path + "/visibility", headers=peer_headers, json={"is_hidden": False}).status_code == 200
    assert client.get(ROOT + "/favorites", headers=peer_headers).json()["total"] == 0
    with Session(c["engine"]) as db:
        assert db.get(User, c["uid"]) is None and db.get(User, c["peer"]) is not None
        for model in (UserSession, WithdrawalChallenge, ChatRoomMember, FavoritePost):
            assert db.scalar(select(func.count()).select_from(model).where(model.user_id == c["uid"])) == 0
        assert db.scalar(select(func.count()).select_from(EmailVerification).where(EmailVerification.email == "account@skku.edu")) == 0
        assert db.scalar(select(func.count()).select_from(RecommendationRun)) == 0
        assert db.scalar(select(func.count()).select_from(RecommendationItem)) == 0
        assert db.scalar(select(func.count()).select_from(PostEmbedding)) == 0
    email = "account@skku.edu"
    client.post("/api/v1/auth/email/send-code", json={"email": email})
    client.post("/api/v1/auth/email/verify", json={"email": email, "code": c["codes"][-1][1]})
    signup = client.post("/api/v1/auth/signup", json={"email": email, "nickname": "작성자", "password": "new-password-123"})
    assert signup.status_code == 201, signup.text
    assert signup.json()["user"]["id"] != str(c["uid"])
    new_headers = {"Authorization": "Bearer " + signup.json()["access_token"]}
    assert client.get(ROOT + "/posts", headers=new_headers).json()["total"] == 0
    assert client.get("/api/v1/chat/rooms?include_hidden=true", headers=new_headers).json()["total"] == 0
    assert client.get(path + "/messages", headers=new_headers).status_code == 404
    assert client.get(chat_image_url, headers=new_headers).status_code == 404


def test_photo_failure_rolls_back_and_restores_already_deleted_files(withdrawal, monkeypatch):
    c = withdrawal
    pid = create_post(c["client"], c["headers"])
    keys = [upload_post(c, pid), upload_post(c, pid)]
    token = start(c)
    verify(c, token)
    original = c["posts"].delete
    calls = []
    def fail_second(key):
        calls.append(key)
        if len(calls) == 2:
            raise ApiError(502, "storage_unavailable", "test failure")
        original(key)
    monkeypatch.setattr(c["posts"], "delete", fail_second)
    assert remove(c, token).status_code == 502
    assert c["client"].get(ROOT, headers=c["headers"]).status_code == 200
    assert c["client"].get("/api/v1/posts/" + pid).status_code == 200
    assert all(c["posts"].download(key) == PNG for key in keys)
    monkeypatch.setattr(c["posts"], "delete", original)
    assert remove(c, token).status_code == 204


def test_database_failure_restores_post_photo_and_account(withdrawal, monkeypatch):
    c = withdrawal
    pid = create_post(c["client"], c["headers"])
    key = upload_post(c, pid)
    token = start(c)
    verify(c, token)
    with Session(c["engine"]) as db:
        user = db.get(User, c["uid"])
        def fail():
            raise RuntimeError("commit failed")
        monkeypatch.setattr(db, "commit", fail)
        with pytest.raises(RuntimeError, match="commit failed"):
            WithdrawalService.withdraw(db, user, token)
        assert db.get(User, c["uid"]) is not None and db.get(Post, UUID(pid)) is not None
        assert c["posts"].download(key) == PNG


def test_last_participant_withdrawal_removes_unreadable_orphan_history(withdrawal):
    c = withdrawal
    client = c["client"]
    data = seed_history(c)
    rooms, peer_room = data[4], data[5]
    first = start(c)
    verify(c, first)
    assert remove(c, first).status_code == 204
    with Session(c["engine"]) as db:
        db.get(User, c["peer"]).password_hash = hash_secret("peer-password-123")
        db.commit()
    last = start(c, c["peer_headers"], "peer-password-123")
    verify(c, last, c["peer_headers"])
    assert remove(c, last, c["peer_headers"]).status_code == 204
    with Session(c["engine"]) as db:
        assert not list(db.scalars(select(ChatRoom).where(ChatRoom.id.in_([UUID(x) for x in [*rooms, peer_room]]))))
        assert db.scalar(select(func.count()).select_from(ChatMessage)) == 0
        assert db.scalar(select(func.count()).select_from(ChatMessageImage)) == 0
    assert not list(c["chats"].root.rglob("*.png"))


@pytest.mark.skipif(not os.getenv("TEST_WITHDRAWAL_DATABASE_URL"), reason="requires a disposable PostgreSQL test DB")
def test_concurrent_deletion_is_single_use(withdrawal):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    c = withdrawal
    token = start(c)
    verify(c, token)
    barrier = Barrier(2)
    def action():
        barrier.wait(timeout=10)
        return remove(c, token).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(action) for _ in range(2)]
        assert sorted(f.result(timeout=20) for f in futures) == [204, 401]


@pytest.mark.skipif(not os.getenv("TEST_WITHDRAWAL_DATABASE_URL"), reason="requires a disposable PostgreSQL test DB")
def test_peer_send_racing_deletion_preserves_closed_history(withdrawal):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    c = withdrawal
    client = c["client"]
    pid = create_post(client, c["headers"])
    room = client.post("/api/v1/chat/rooms", headers=c["peer_headers"], json={"post_id": pid}).json()["id"]
    token = start(c)
    verify(c, token)
    barrier = Barrier(2)
    def remove_account():
        barrier.wait(timeout=10)
        return remove(c, token).status_code
    def send():
        barrier.wait(timeout=10)
        return client.post(f"/api/v1/chat/rooms/{room}/messages", headers=c["peer_headers"], json={"content": "racing message"}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        deleted, sent = pool.submit(remove_account), pool.submit(send)
        assert deleted.result(timeout=20) == 204
        assert sent.result(timeout=20) in (201, 409)
    assert client.get(f"/api/v1/chat/rooms/{room}", headers=c["peer_headers"]).json()["status"] == "CLOSED"
    assert client.get(f"/api/v1/chat/rooms/{room}/messages", headers=c["peer_headers"]).status_code == 200
