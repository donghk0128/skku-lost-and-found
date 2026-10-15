"""Exercise post routes through FastAPI using an isolated in-memory database."""

import os
from collections.abc import Generator
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

# Set this before importing application modules that read database settings.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough")

from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app
from app.posts.model import Post
from app.users.model import User


@pytest.fixture()
def api_client() -> Generator[tuple[TestClient, Engine], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def test_get_db() -> Generator[Session, None, None]:
        with Session(engine) as db:
            yield db

    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = test_get_db
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        if original_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = original_override
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_author(engine: Engine) -> UUID:
    with Session(engine) as db:
        author = User(
            email="api-post-author@g.skku.edu",
            password_hash="test-hash",
            nickname="작성자",
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(author)
        db.commit()
        return author.id


def post_payload() -> dict[str, str]:
    return {
        "post_type": "LOST",
        "title": "  에어팟 분실  ",
        "description": "  검은색 케이스  ",
    }


def test_create_and_read_post_through_http(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    author_id = create_author(engine)
    headers = {"Authorization": f"Bearer {create_access_token(author_id)}"}

    created_response = client.post("/api/v1/posts", headers=headers, json=post_payload())
    assert created_response.status_code == 201
    created = created_response.json()
    assert created["author_id"] == str(author_id)
    assert created["post_type"] == "LOST"
    assert created["title"] == "에어팟 분실"
    assert created["description"] == "검은색 케이스"
    assert created["status"] == "OPEN"
    assert created["creation_method"] == "MANUAL"

    with Session(engine) as db:
        saved = db.get(Post, UUID(created["id"]))
        assert saved is not None
        assert saved.author_id == author_id

    read_response = client.get(f"/api/v1/posts/{created['id']}")
    assert read_response.status_code == 200
    assert read_response.json() == created


def test_create_requires_login_and_rejects_invalid_input(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    unauthenticated = client.post("/api/v1/posts", json=post_payload())
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "authentication_required"

    author_id = create_author(engine)
    headers = {"Authorization": f"Bearer {create_access_token(author_id)}"}

    forged_author = client.post(
        "/api/v1/posts",
        headers=headers,
        json={**post_payload(), "author_id": str(uuid4())},
    )
    assert forged_author.status_code == 422
    assert forged_author.json()["error"]["code"] == "validation_error"

    blank_title = client.post(
        "/api/v1/posts",
        headers=headers,
        json={**post_payload(), "title": "   "},
    )
    assert blank_title.status_code == 422

    with Session(engine) as db:
        assert db.scalars(select(Post)).all() == []


def test_read_returns_404_for_missing_or_deleted_post(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    missing = client.get(f"/api/v1/posts/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "post_not_found"

    author_id = create_author(engine)
    headers = {"Authorization": f"Bearer {create_access_token(author_id)}"}
    created = client.post("/api/v1/posts", headers=headers, json=post_payload())
    assert created.status_code == 201
    post_id = created.json()["id"]

    with Session(engine) as db:
        post = db.get(Post, UUID(post_id))
        assert post is not None
        post.deleted_at = datetime.now(timezone.utc)
        db.commit()

    deleted = client.get(f"/api/v1/posts/{post_id}")
    assert deleted.status_code == 404
    assert deleted.json()["error"]["code"] == "post_not_found"
