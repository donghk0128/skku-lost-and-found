"""Test embedding lifecycle without calling the paid or free external API."""

import os
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough")

from app.core.database import Base
from app.matching.embedding import DIMENSIONS, EmbeddingError, embed_text
from app.matching.model import PostEmbedding
from app.posts.schemas import PostCreateRequest, PostUpdateRequest
from app.posts.service import PostService
from app.users.model import User


def test_gemini_request_uses_similarity_task_and_normalizes_768_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        assert url.endswith("/gemini-embedding-001:embedContent")
        assert kwargs["headers"] == {"x-goog-api-key": "test-key"}
        body = kwargs["json"]
        assert isinstance(body, dict)
        assert body["taskType"] == "SEMANTIC_SIMILARITY"
        assert body["outputDimensionality"] == DIMENSIONS
        return httpx.Response(
            200,
            json={"embedding": {"values": [3.0, 4.0] + [0.0] * 766}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.matching.embedding.httpx.post", fake_post)
    vector = embed_text("검은색 지갑", "test-key", 5)
    assert len(vector) == DIMENSIONS
    assert vector[:2] == pytest.approx([0.6, 0.8])


def test_gemini_rejects_wrong_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.matching.embedding.httpx.post",
        lambda url, **kwargs: httpx.Response(
            200,
            json={"embedding": {"values": [1.0]}},
            request=httpx.Request("POST", url),
        ),
    )
    with pytest.raises(EmbeddingError):
        embed_text("지갑", "test-key", 5)


def test_post_creation_and_text_update_refresh_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    calls: list[str] = []
    monkeypatch.setattr(
        "app.matching.embedding.get_settings",
        lambda: SimpleNamespace(gemini_api_key="test-key", gemini_embedding_timeout_seconds=5),
    )

    def fake_embed(text: str, api_key: str, timeout: float) -> list[float]:
        calls.append(text)
        return [1.0 if "검은" in text else 0.0, 0.0 if "검은" in text else 1.0] + [0.0] * 766

    monkeypatch.setattr("app.matching.embedding.embed_text", fake_embed)
    try:
        with Session(engine) as db:
            author = User(
                email="embedding-author@g.skku.edu",
                password_hash="test-hash",
                nickname="작성자",
                email_verified_at=datetime.now(timezone.utc),
            )
            db.add(author)
            db.commit()
            post = PostService.create(
                db,
                PostCreateRequest(post_type="LOST", title="검은 지갑", description="학생회관"),
                author,
            )
            first = db.get(PostEmbedding, post.id)
            assert first is not None
            assert first.embedding[:2] == [1.0, 0.0]
            assert len(calls) == 1

            PostService.update(db, post.id, PostUpdateRequest(location_text="도서관"), author)
            assert len(calls) == 1

            PostService.update(db, post.id, PostUpdateRequest(title="파란 지갑"), author)
            updated = db.get(PostEmbedding, post.id)
            assert updated is not None
            assert updated.embedding[:2] == [0.0, 1.0]
            assert len(calls) == 2

            monkeypatch.setattr(
                "app.matching.embedding.embed_text",
                lambda *args: (_ for _ in ()).throw(EmbeddingError("rate limited")),
            )
            PostService.update(db, post.id, PostUpdateRequest(title="빨간 지갑"), author)
            assert db.get(PostEmbedding, post.id) is None
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()

