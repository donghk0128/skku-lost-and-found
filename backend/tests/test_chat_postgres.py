"""Opt-in concurrency checks against a disposable, migrated PostgreSQL database."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.chat.model import ChatMessage, ChatMessageImage, ChatRoom, ChatRoomMember
from app.chat.service import ChatService
from app.core.errors import ApiError
from app.posts.model import Post, now_utc
from app.posts.service import PostService
from app.users.model import User

pytestmark = pytest.mark.skipif(not os.getenv("TEST_CHAT_DATABASE_URL"), reason="requires a disposable migrated PostgreSQL test DB")


@pytest.fixture()
def pg_chat():
    url = make_url(os.environ["TEST_CHAT_DATABASE_URL"])
    assert url.get_backend_name() == "postgresql" and url.database.endswith("_test"), "Use a disposable *_test database"
    engine = create_engine(url, connect_args={"options": "-c lock_timeout=5000 -c statement_timeout=10000"})
    user_ids, post_id = [], None
    try:
        with Session(engine) as db:
            users = [User(email=f"chat-pg-{uuid4()}@skku.edu", password_hash="test", nickname=f"테스트-{uuid4().hex[:12]}", email_verified_at=now_utc()) for _ in range(3)]
            db.add_all(users)
            db.flush()
            user_ids = [u.id for u in users]
            post = Post(author_id=user_ids[0], post_type="FOUND", title="테스트", description="동시성 검증")
            db.add(post)
            db.commit()
            post_id = post.id
        yield engine, user_ids, post_id
    finally:
        if post_id is not None:
            with Session(engine) as db:
                room_ids = select(ChatRoom.id).where(ChatRoom.post_id == post_id)
                message_ids = select(ChatMessage.id).where(ChatMessage.room_id.in_(room_ids))
                db.execute(delete(ChatMessageImage).where(ChatMessageImage.message_id.in_(message_ids)))
                db.execute(delete(ChatMessage).where(ChatMessage.room_id.in_(room_ids)))
                db.execute(delete(ChatRoomMember).where(ChatRoomMember.room_id.in_(room_ids)))
                db.execute(delete(ChatRoom).where(ChatRoom.post_id == post_id))
                db.execute(delete(Post).where(Post.id == post_id))
                db.execute(delete(User).where(User.id.in_(user_ids)))
                db.commit()
        engine.dispose()


def race(*actions):
    barrier = Barrier(len(actions))
    def run(action):
        barrier.wait(timeout=10)
        return action()
    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        futures = [pool.submit(run, action) for action in actions]
        return [future.result(timeout=20) for future in futures]


def test_concurrent_creation_returns_one_room(pg_chat):
    engine, users, post = pg_chat
    def create():
        with Session(engine) as db:
            return ChatService.create(db, post, users[1]).id
    assert len(set(race(create, create, create))) == 1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ChatRoom).where(ChatRoom.post_id == post)) == 1


def test_concurrent_messages_have_unique_order(pg_chat):
    engine, users, post = pg_chat
    with Session(engine) as db:
        room = ChatService.create(db, post, users[1]).id
    def send():
        with Session(engine) as db:
            return ChatService.send(db, room, users[1], "동시 메시지").sequence
    assert sorted(race(send, send, send, send)) == [1, 2, 3, 4]


def test_send_and_close_are_serialized(pg_chat):
    engine, users, post = pg_chat
    with Session(engine) as db:
        room = ChatService.create(db, post, users[1]).id
    def send():
        with Session(engine) as db:
            try:
                return ChatService.send(db, room, users[1], "종료 경합").sequence
            except ApiError as error:
                assert error.code == "chat_room_closed"
                return 0
    def close():
        with Session(engine) as db:
            return ChatService.close(db, room, users[0], "GENERAL").status
    result = race(send, close)
    assert result[1] == "CLOSED"
    with Session(engine) as db:
        with pytest.raises(ApiError) as caught:
            ChatService.send(db, room, users[1], "종료 이후")
        assert caught.value.code == "chat_room_closed"
        db.rollback()
        messages = list(db.scalars(select(ChatMessage).where(ChatMessage.room_id == room)))
        closed_at = db.get(ChatRoom, room).closed_at
        assert all(message.created_at <= closed_at for message in messages)


@pytest.mark.parametrize("operation", ["delete", "complete"])
def test_creation_racing_post_lifecycle_preserves_policy(pg_chat, operation):
    engine, users, post = pg_chat
    def create():
        with Session(engine) as db:
            try:
                return ChatService.create(db, post, users[1]).status
            except ApiError as error:
                assert error.code in ("post_not_found", "post_completed")
                return error.code
    def change_post():
        with Session(engine) as db:
            owner = db.get(User, users[0])
            try:
                if operation == "delete":
                    PostService.delete(db, post, owner)
                else:
                    PostService.complete(db, post, owner)
                return "changed"
            except ApiError as error:
                assert operation == "delete" and error.code == "active_chat_rooms"
                return "blocked"
    race(create, change_post)
    with Session(engine) as db:
        saved = db.get(Post, post)
        active = db.scalar(select(func.count()).select_from(ChatRoom).where(ChatRoom.post_id == post, ChatRoom.status == "ACTIVE"))
        if saved.deleted_at is not None or saved.status == "COMPLETED":
            assert active == 0
        else:
            assert operation == "delete" and active == 1


def test_database_rejects_incomplete_closed_state(pg_chat):
    engine, users, post = pg_chat
    with Session(engine) as db:
        room = ChatService.create(db, post, users[1]).id
        saved = db.get(ChatRoom, room)
        saved.status, saved.closed_at = "CLOSED", now_utc()
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        message = ChatMessage(room_id=room, sender_id=users[1], sequence=1, message_type="IMAGE")
        db.add(message)
        db.flush()
        db.add(ChatMessageImage(message_id=message.id, storage_key="invalid", content_type="text/plain", position=0))
        with pytest.raises(IntegrityError):
            db.commit()


def test_concurrent_group_retries_create_one_message(pg_chat, monkeypatch, tmp_path):
    from app.posts.storage import LocalPostImageStorage
    monkeypatch.setattr("app.chat.service.get_chat_image_storage", lambda: LocalPostImageStorage(tmp_path))
    engine, users, post = pg_chat
    with Session(engine) as db:
        room = ChatService.create(db, post, users[1]).id
    def send():
        with Session(engine) as db:
            return ChatService.send(db, room, users[1], images=[(b"\x89PNG\r\n\x1a\n", "image/png")] * 3, client_message_id="retry-group").id
    assert len(set(race(send, send, send))) == 1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ChatMessage).where(ChatMessage.room_id == room)) == 1
        assert len(list(tmp_path.rglob("*.png"))) == 3


def test_concurrent_text_retries_create_one_message(pg_chat):
    engine, users, post = pg_chat
    with Session(engine) as db:
        room = ChatService.create(db, post, users[1]).id
    def send():
        with Session(engine) as db:
            return ChatService.send(db, room, users[1], "같은 텍스트 재시도", client_message_id="same-text-request").id
    assert len(set(race(send, send, send))) == 1
