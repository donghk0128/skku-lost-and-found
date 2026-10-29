"""Exercise AI draft routes without contacting an external model provider."""

import os
from collections.abc import Generator
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough")

from app.ai.router import get_draft_provider
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.integrations.ai.core.providers import FakeProvider, ProviderError
from app.integrations.ai.core.schemas import PostDraft
from app.main import app
from app.posts.model import Category, Post
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

    original_db_override = app.dependency_overrides.get(get_db)
    original_provider_override = app.dependency_overrides.get(get_draft_provider)
    app.dependency_overrides[get_db] = test_get_db
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        if original_db_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = original_db_override
        if original_provider_override is None:
            app.dependency_overrides.pop(get_draft_provider, None)
        else:
            app.dependency_overrides[get_draft_provider] = original_provider_override
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_author(engine: Engine) -> UUID:
    with Session(engine) as db:
        author = User(
            email="ai-api-author@g.skku.edu",
            password_hash="test-hash",
            nickname="작성자",
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(author)
        db.commit()
        return author.id


def fake_provider() -> FakeProvider:
    return FakeProvider(
        PostDraft(
            title="에어팟 케이스 분실",
            description="자연어 설명에서 만든 AI 초안입니다.",
            item_name="에어팟 케이스",
            category_code="ELECTRONICS",
            location_text="모델이 추측한 장소",
            event_start_at=datetime(2026, 10, 26, 10, tzinfo=timezone.utc),
            event_end_at=datetime(2026, 10, 26, 10, tzinfo=timezone.utc),
            keywords=["검은색", "에어팟"],
            missing_fields=[],
            warnings=[],
        )
    )


class ErrorProvider:
    def generate(self, _request: object) -> object:
        raise ProviderError("timeout")


def test_ai_draft_uses_confirmed_location_and_time(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    author_id = create_author(engine)
    with Session(engine) as db:
        db.add(Category(id=1, code="ELECTRONICS", name="전자기기"))
        db.commit()
    app.dependency_overrides[get_draft_provider] = fake_provider

    response = client.post(
        "/api/v1/ai/post-drafts",
        headers={"Authorization": f"Bearer {create_access_token(author_id)}"},
        json={
            "post_type": "LOST",
            "natural_language": "어제 도서관에서 검은색 에어팟 케이스를 잃어버렸어요.",
            "confirmed_location": {
                "text": "중앙학술정보관 3층",
                "latitude": "37.294123",
                "longitude": "126.975456",
            },
            "confirmed_event_start_at": "2026-10-26T21:30:00+09:00",
            "confirmed_event_end_at": "2026-10-26T21:30:00+09:00",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["category_id"] == 1
    assert body["category_code"] == "ELECTRONICS"
    assert body["location_text"] == "중앙학술정보관 3층"
    assert body["latitude"] == 37.294123
    assert body["longitude"] == 126.975456
    assert body["event_start_at"] == "2026-10-26T21:30:00+09:00"
    assert body["event_end_at"] == "2026-10-26T21:30:00+09:00"


def test_ai_draft_requires_login_and_converts_provider_errors(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    unauthenticated = client.post(
        "/api/v1/ai/post-drafts",
        json={"post_type": "LOST", "natural_language": "열쇠를 잃어버렸어요."},
    )
    assert unauthenticated.status_code == 401

    author_id = create_author(engine)
    app.dependency_overrides[get_draft_provider] = ErrorProvider
    response = client.post(
        "/api/v1/ai/post-drafts",
        headers={"Authorization": f"Bearer {create_access_token(author_id)}"},
        json={"post_type": "LOST", "natural_language": "열쇠를 잃어버렸어요."},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_timeout"


def test_ai_chat_asks_for_missing_fact_and_becomes_ready(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    author_id = create_author(engine)
    with Session(engine) as db:
        db.add(Category(id=1, code="ELECTRONICS", name="전자기기"))
        db.commit()
    token = create_access_token(author_id)

    incomplete = fake_provider()
    incomplete.draft.missing_fields = ["location", "event_time"]
    incomplete.draft.location_text = None
    incomplete.draft.event_start_at = None
    incomplete.draft.event_end_at = None
    app.dependency_overrides[get_draft_provider] = lambda: incomplete
    response = client.post(
        "/api/v1/ai/post-draft-chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"post_type": "LOST", "messages": [{"role": "user", "content": "에어팟을 잃어버렸어요."}]},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "NEEDS_INPUT"
    assert "어디" in response.json()["assistant_message"]

    app.dependency_overrides[get_draft_provider] = fake_provider
    response = client.post(
        "/api/v1/ai/post-draft-chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "post_type": "LOST",
            "messages": [
                {"role": "user", "content": "에어팟을 잃어버렸어요."},
                {"role": "user", "content": "어제 중앙도서관 3층이에요."},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "READY"
    assert response.json()["draft"]["category_code"] == "ELECTRONICS"


def test_ai_chat_requires_login_and_rejects_empty_history(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    response = client.post(
        "/api/v1/ai/post-draft-chat",
        json={"post_type": "FOUND", "messages": [{"role": "user", "content": "열쇠를 주웠어요."}]},
    )
    assert response.status_code == 401

    author_id = create_author(engine)
    response = client.post(
        "/api/v1/ai/post-draft-chat",
        headers={"Authorization": f"Bearer {create_access_token(author_id)}"},
        json={"post_type": "FOUND", "messages": []},
    )
    assert response.status_code == 422


def test_ai_assisted_post_is_labeled_when_persisted(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    author_id = create_author(engine)
    response = client.post(
        "/api/v1/posts/ai-assisted",
        headers={"Authorization": f"Bearer {create_access_token(author_id)}"},
        json={"post_type": "FOUND", "title": "AI 초안", "description": "사용자가 확인한 글입니다."},
    )
    assert response.status_code == 201
    assert response.json()["creation_method"] == "AI_ASSISTED"

    with Session(engine) as db:
        saved = db.get(Post, UUID(response.json()["id"]))
        assert saved is not None
        assert saved.creation_method == "AI_ASSISTED"
