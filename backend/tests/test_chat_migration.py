"""Opt-in real migration test with legacy rows in a separate empty *_test DB."""

import os
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

pytestmark = pytest.mark.skipif(not os.getenv("TEST_CHAT_MIGRATION_DATABASE_URL"), reason="requires a separate empty migration test database")


def test_legacy_photo_backfill_roundtrip_and_group_downgrade_guard():
    url = os.environ["TEST_CHAT_MIGRATION_DATABASE_URL"]
    parsed = make_url(url)
    assert parsed.database.endswith("_test") and parsed.get_backend_name() == "postgresql"
    engine = create_engine(url)
    env = {**os.environ, "DATABASE_URL": url}
    def migrate(revision, direction="upgrade", success=True):
        result = subprocess.run([sys.executable, "-m", "alembic", direction, revision], env=env, capture_output=True, text=True, timeout=30)
        assert (result.returncode == 0) == success, result.stderr
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname='public'")) == 0, "Use an empty test database"
        migrate("0006_create_chat_tables")
        owner, requester, post, room, message = [uuid4() for _ in range(5)]
        key = f"{room}/{uuid4()}.png"
        with engine.begin() as connection:
            for user_id in (owner, requester):
                connection.execute(text("INSERT INTO users (id,email,password_hash,nickname,email_verified_at) VALUES (:id,:email,'test','test',now())"), {"id": user_id, "email": f"{user_id}@skku.edu"})
            connection.execute(text("INSERT INTO posts (id,author_id,post_type,title,description) VALUES (:id,:owner,'FOUND','test','test')"), {"id": post, "owner": owner})
            connection.execute(text("INSERT INTO chat_rooms (id,post_id,owner_id,requester_id) VALUES (:id,:post,:owner,:requester)"), {"id": room, "post": post, "owner": owner, "requester": requester})
            connection.execute(text("INSERT INTO chat_messages (id,room_id,sender_id,sequence,message_type,image_storage_key,image_content_type) VALUES (:id,:room,:sender,1,'IMAGE',:key,'image/png')"), {"id": message, "room": room, "sender": owner, "key": key})
        # This round-trip tests 0007 only, independently of later revisions.
        migrate("0007_create_chat_message_images")
        with engine.connect() as connection:
            row = connection.execute(text("SELECT message_id,storage_key,content_type,position FROM chat_message_images")).one()
            assert row == (message, key, "image/png", 0)
        migrate("0006_create_chat_tables", "downgrade")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT image_storage_key FROM chat_messages WHERE id=:id"), {"id": message}) == key
        migrate("0007_create_chat_message_images")
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO chat_message_images (id,message_id,storage_key,content_type,position) VALUES (:id,:message,:key,'image/png',1)"), {"id": uuid4(), "message": message, "key": f"{room}/{uuid4()}.png"})
        migrate("0006_create_chat_tables", "downgrade", success=False)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0007_create_chat_message_images"
            assert connection.scalar(text("SELECT count(*) FROM chat_message_images")) == 2
    finally:
        engine.dispose()
