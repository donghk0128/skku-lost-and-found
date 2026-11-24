"""Opt-in worker concurrency checks in an isolated temporary PostgreSQL schema."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import Base
from app.notifications.model import PushDelivery, PushDevice, PushNotification
from app.notifications.service import deliver_next, enqueue_post_notifications
from app.posts.model import Post
from app.users.model import KeywordCondition, User, UserSession, now_utc

pytestmark = pytest.mark.skipif(not os.getenv("TEST_PUSH_DATABASE_URL"), reason="requires opt-in PostgreSQL connection")


def test_workers_skip_locked_and_account_deletion_cascades(monkeypatch):
    monkeypatch.setattr(get_settings(), "push_enabled", True)
    schema = "push_test_" + uuid4().hex
    admin = create_engine(os.environ["TEST_PUSH_DATABASE_URL"])
    engine = admin.execution_options(schema_translate_map={None: schema})
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            owner = User(email="owner@skku.edu", nickname="owner", password_hash="test", email_verified_at=now_utc())
            author = User(email="author@skku.edu", nickname="author", password_hash="test", email_verified_at=now_utc())
            db.add_all([owner, author]); db.flush()
            owner_id = owner.id
            session = UserSession(user_id=owner.id, refresh_token_hash="test", expires_at=now_utc() + timedelta(days=1))
            db.add(session); db.flush()
            db.add(KeywordCondition(user_id=owner.id, post_type="FOUND", conditions={"q": "에어팟"},
                notification_enabled=True, notification_enabled_at=now_utc()))
            db.add(PushDevice(id=uuid4(), user_id=owner.id, session_id=session.id, platform="android", fid="testFID", fid_hash="test-hash"))
            db.commit()
            post = Post(author_id=author.id, post_type="FOUND", title="에어팟", description="test")
            db.add(post); db.flush()
            enqueue_post_notifications(db, post)
            db.commit()
        sending, release = Event(), Event()
        class Sender:
            calls = 0
            def send(self, *_):
                self.calls += 1
                sending.set()
                assert release.wait(10)
        sender = Sender()
        def work():
            with Session(engine) as db:
                return deliver_next(db, sender)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(work)
            assert sending.wait(10)
            try:
                assert pool.submit(work).result(timeout=5) is False
            finally:
                release.set()
            assert first.result(timeout=10) is True
        assert sender.calls == 1
        with Session(engine) as db:
            assert db.scalar(select(PushDelivery)).status == "SENT"
            db.execute(delete(User).where(User.id == owner_id))
            db.commit()
            assert db.scalar(select(PushDevice)) is None
            assert db.scalar(select(PushNotification)) is None
            assert db.scalar(select(PushDelivery)) is None
    finally:
        # The schema name is generated here, never provided by a caller.
        assert schema.startswith("push_test_") and len(schema) == 42
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()
