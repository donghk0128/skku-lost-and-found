"""Check the home ranking contract and durable, deduplicated run records."""

import os
from collections.abc import Generator
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough")

from app.auth.service import get_current_user
from app.core.database import Base, get_db
from app.main import app
from app.matching.model import RecommendationItem, RecommendationRun
from app.posts.model import Category, Post
from app.users.model import User


@pytest.fixture()
def client_and_engine() -> Generator[tuple[TestClient, object, User, dict[str, Post]], None, None]:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        author = User(email="ranking@g.skku.edu", password_hash="test", nickname="tester", email_verified_at=datetime.now(timezone.utc))
        other_user = User(email="other@g.skku.edu", password_hash="test", nickname="other", email_verified_at=datetime.now(timezone.utc))
        db.add_all([author, other_user, Category(id=1, code="ELECTRONICS", name="전자기기"), Category(id=2, code="BAG", name="가방")])
        db.flush()
        posts = {
            "source": Post(author_id=author.id, post_type="FOUND", title="검은 에어팟 습득", description="도서관 앞", item_name="에어팟", category_id=1),
            "best": Post(author_id=other_user.id, post_type="LOST", title="검은 에어팟 분실", description="도서관 앞", item_name="에어팟", category_id=1),
            "bag": Post(author_id=other_user.id, post_type="LOST", title="가방 분실", description="도서관 앞", item_name="가방", category_id=2),
            "completed": Post(author_id=other_user.id, post_type="LOST", title="완료된 에어팟", description="도서관", status="COMPLETED"),
            "deleted": Post(author_id=other_user.id, post_type="LOST", title="삭제된 에어팟", description="도서관", deleted_at=datetime.now(timezone.utc)),
            "other_source": Post(author_id=other_user.id, post_type="FOUND", title="남의 습득글", description="도서관"),
        }
        db.add_all(posts.values())
        db.commit()
        db.refresh(author)
        for post in posts.values():
            db.refresh(post)

    def test_db() -> Generator[Session, None, None]:
        with Session(engine) as db:
            yield db

    old_db = app.dependency_overrides.get(get_db)
    old_user = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_current_user] = lambda: author
    try:
        with TestClient(app) as client:
            yield client, engine, author, posts
    finally:
        if old_db is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = old_db
        if old_user is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = old_user
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_my_posts_and_filtered_ranking(client_and_engine) -> None:
    client, engine, author, posts = client_and_engine
    mine = client.get("/api/v1/posts/mine?post_type=FOUND")
    assert mine.status_code == 200
    assert [item["id"] for item in mine.json()["items"]] == [str(posts["source"].id)]

    url = f"/api/v1/posts/{posts['source'].id}/ranked-candidates"
    result = client.get(url)
    assert result.status_code == 200
    body = result.json()
    assert body["algorithm_version"] == "hybrid-v3"
    assert body["total"] == 2
    assert [item["post"]["id"] for item in body["items"]] == [str(posts["best"].id), str(posts["bag"].id)]
    assert body["items"][0]["rank"] == 1
    assert "SAME_CATEGORY" in body["items"][0]["reasons"]
    assert body["items"][0]["semantic_score"] is None

    page = client.get(url + "?limit=1&offset=1")
    assert page.json()["items"][0]["rank"] == 2
    assert page.json()["run_id"] == body["run_id"]
    assert client.get(url + "?category_id=2").json()["items"][0]["post"]["id"] == str(posts["bag"].id)
    assert [item["post"]["id"] for item in client.get(url + "?q=에어팟").json()["items"]] == [str(posts["best"].id)]
    with Session(engine) as db:
        assert len(db.scalars(select(RecommendationRun)).all()) == 3
        assert len(db.scalars(select(RecommendationItem).where(RecommendationItem.run_id == UUID(body["run_id"]))).all()) == 2
        assert db.get(RecommendationRun, UUID(body["run_id"])).algorithm_version == "hybrid-v3"


def test_source_ownership_status_and_query_validation(client_and_engine) -> None:
    client, _, _, posts = client_and_engine
    base = "/api/v1/posts/"
    assert client.get(base + str(posts["other_source"].id) + "/ranked-candidates").status_code == 403
    assert client.get(base + str(posts["completed"].id) + "/ranked-candidates").status_code == 403
    assert client.get(base + str(uuid4()) + "/ranked-candidates").status_code == 404
    assert client.get(base + str(posts["source"].id) + "/ranked-candidates?q=%20").status_code == 422
    assert client.get(base + str(posts["source"].id) + "/ranked-candidates?limit=0").status_code == 422


def test_changed_candidate_creates_new_run(client_and_engine) -> None:
    client, engine, _, posts = client_and_engine
    url = f"/api/v1/posts/{posts['source'].id}/ranked-candidates"
    first = client.get(url).json()["run_id"]
    with Session(engine) as db:
        post = db.get(Post, posts["bag"].id)
        post.title = "새로운 가방"
        db.commit()
    second = client.get(url).json()["run_id"]
    assert second != first


def test_home_ranking_scores_all_filtered_candidates(client_and_engine, monkeypatch: pytest.MonkeyPatch) -> None:
    client, engine, _, posts = client_and_engine
    with Session(engine) as db:
        db.add_all(
            Post(author_id=posts["best"].author_id, post_type="LOST", title=f"후보 {index}", description="도서관")
            for index in range(55)
        )
        db.commit()
    compared = []

    def fake_similarities(db, source, candidate_ids):
        compared.extend(candidate_ids)
        return {}

    monkeypatch.setattr("app.matching.service.MatchingRepository.cosine_similarities", fake_similarities)
    response = client.get(f"/api/v1/posts/{posts['source'].id}/ranked-candidates?limit=100")
    assert response.status_code == 200
    assert response.json()["total"] == 57
    assert len(response.json()["items"]) == 57
    assert len(compared) == 57
