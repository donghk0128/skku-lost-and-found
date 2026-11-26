"""Opt-in integration check against a disposable, migrated local PostgreSQL DB."""

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.chat.model import ChatRoom, ChatRoomMember, ReturnPair
from app.chat.service import ChatService
from app.events.model import EventLog
from app.events.schemas import EventCreate
from app.events.service import record_business_event, store_client_event
from app.posts.model import Post
from app.users.model import User

pytestmark = pytest.mark.skipif(not os.getenv("TEST_EVENT_DATABASE_URL"), reason="requires disposable PostgreSQL test DB")


def test_migrated_postgres_stores_events_and_confirmed_pair():
    url = make_url(os.environ["TEST_EVENT_DATABASE_URL"])
    assert url.get_backend_name() == "postgresql" and url.host in ("localhost", "127.0.0.1")
    assert url.database.endswith("_test"), "Use only a disposable local *_test database"
    engine = create_engine(url)
    user_ids, post_ids, room_id = [], [], None
    try:
        with Session(engine) as db:
            assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0018_return_pairs"
            users = [User(email=f"event-pg-{uuid4()}@skku.edu", password_hash="test",
                          nickname=f"검증-{uuid4().hex[:12]}", email_verified_at=datetime.now(timezone.utc)) for _ in range(2)]
            db.add_all(users)
            db.flush()
            user_ids = [user.id for user in users]
            posts = [Post(author_id=user_ids[0], post_type="LOST", title="분실", description="검증"),
                     Post(author_id=user_ids[1], post_type="FOUND", title="습득", description="검증")]
            db.add_all(posts)
            db.commit()
            post_ids = [post.id for post in posts]

            room_id = ChatService.create(db, post_ids[0], user_ids[1]).id
            proposed = ChatService.propose_pair(db, room_id, user_ids[0], post_ids[1])
            assert proposed.return_pair.status == "PENDING"
            confirmed = ChatService.confirm_pair(db, room_id, user_ids[1])
            assert confirmed.return_pair.status == "CONFIRMED"
            assert confirmed.close_reason == "RETURNED"
            record_business_event(db, user_ids[1], "match_confirmed", confirmed.return_pair.id,
                                  source_post_id=post_ids[0], candidate_post_id=post_ids[1])

            event = EventCreate(event_id=uuid4(), event_type="screen_view", screen="home",
                                visit_id=uuid4(), occurred_at=datetime.now(timezone.utc))
            assert store_client_event(db, user_ids[0], event) is True
            assert store_client_event(db, user_ids[0], event) is False
            saved = db.get(EventLog, event.event_id)
            assert saved.received_at is not None and saved.occurred_at is not None
            assert db.scalar(select(ReturnPair).where(ReturnPair.room_id == room_id)).status == "CONFIRMED"
            assert all(db.get(Post, post_id).status == "COMPLETED" for post_id in post_ids)
    finally:
        with Session(engine) as db:
            if user_ids:
                db.execute(delete(EventLog).where(EventLog.user_id.in_(user_ids)))
            if room_id:
                db.execute(delete(ReturnPair).where(ReturnPair.room_id == room_id))
                db.execute(delete(ChatRoomMember).where(ChatRoomMember.room_id == room_id))
                db.execute(delete(ChatRoom).where(ChatRoom.id == room_id))
            if post_ids:
                db.execute(delete(Post).where(Post.id.in_(post_ids)))
            if user_ids:
                db.execute(delete(User).where(User.id.in_(user_ids)))
            db.commit()
        engine.dispose()
