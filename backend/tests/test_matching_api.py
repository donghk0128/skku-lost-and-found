"""Exercise recommendation ranking and its public API with an isolated database."""

import os
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough")

from app.core.database import Base, get_db
from app.main import app
from app.matching.scoring import score_posts
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


def _seed_posts(engine: Engine) -> dict[str, UUID]:
    event_time = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    with Session(engine) as db:
        author = User(
            email="matching-author@g.skku.edu",
            password_hash="test-hash",
            nickname="작성자",
            email_verified_at=event_time,
        )
        db.add(author)
        db.add_all([
            Category(id=1, code="ELECTRONICS", name="전자기기"),
            Category(id=2, code="BAG", name="가방"),
        ])
        db.flush()
        common = {"author_id": author.id, "event_start_at": event_time, "event_end_at": event_time}
        posts = {
            "source": Post(
                **common, post_type="LOST", title="검은 무선 이어폰 분실", description="학생회관 근처",
                item_name="무선 이어폰", category_id=1, latitude=Decimal("37.588000"), longitude=Decimal("126.993000"),
            ),
            "best": Post(
                **common, post_type="FOUND", title="무선이어폰 습득", description="검은 케이스 학생회관",
                item_name="무선이어폰", category_id=1, latitude=Decimal("37.588100"), longitude=Decimal("126.993100"),
            ),
            "other": Post(
                **common, post_type="FOUND", title="파란 가방 습득", description="멀리서 발견",
                item_name="가방", category_id=2, latitude=Decimal("37.700000"), longitude=Decimal("127.100000"),
            ),
            "completed": Post(
                **common, post_type="FOUND", title="무선 이어폰 습득", description="학생회관",
                item_name="무선이어폰", category_id=1, status="COMPLETED",
            ),
            "deleted": Post(
                **common, post_type="FOUND", title="무선 이어폰 습득", description="학생회관",
                item_name="무선이어폰", category_id=1, deleted_at=event_time,
            ),
            "same_type": Post(
                **common, post_type="LOST", title="무선 이어폰 분실", description="학생회관",
                item_name="무선이어폰", category_id=1,
            ),
        }
        db.add_all(posts.values())
        db.commit()
        return {name: post.id for name, post in posts.items()}


def test_recommendations_rank_opposite_open_posts_and_ignore_ineligible_posts(
    api_client: tuple[TestClient, Engine],
) -> None:
    client, engine = api_client
    ids = _seed_posts(engine)

    response = client.get(f"/api/v1/posts/{ids['source']}/recommendations")
    assert response.status_code == 200
    assert response.json()["source_post_id"] == str(ids["source"])
    items = response.json()["items"]
    assert [item["post"]["id"] for item in items] == [str(ids["best"]), str(ids["other"])]
    assert items[0]["score"] > items[1]["score"]
    assert all(0 <= item["score"] <= 1 for item in items)
    assert len(client.get(f"/api/v1/posts/{ids['source']}/recommendations?limit=1").json()["items"]) == 1


def test_recommendations_handle_completed_and_missing_sources(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    ids = _seed_posts(engine)

    completed = client.get(f"/api/v1/posts/{ids['completed']}/recommendations")
    assert completed.status_code == 200
    assert completed.json()["items"] == []
    assert client.get(f"/api/v1/posts/{ids['deleted']}/recommendations").status_code == 404
    assert client.get(f"/api/v1/posts/{uuid4()}/recommendations").status_code == 404
    assert client.get(f"/api/v1/posts/{ids['best']}/recommendations?limit=0").status_code == 422

    found_source = client.get(f"/api/v1/posts/{ids['best']}/recommendations")
    assert found_source.status_code == 200
    assert {item["post"]["id"] for item in found_source.json()["items"]} == {
        str(ids["source"]), str(ids["same_type"])
    }


def test_scoring_uses_time_and_distance_without_requiring_them() -> None:
    event_time = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    common = {"post_type": "LOST", "title": "무선 이어폰", "description": "검은 케이스", "category_id": 1}
    source = Post(**common, latitude=Decimal("37.588000"), longitude=Decimal("126.993000"), event_start_at=event_time, event_end_at=event_time)
    near = Post(**common, latitude=Decimal("37.588100"), longitude=Decimal("126.993100"), event_start_at=event_time, event_end_at=event_time)
    far = Post(
        **common, latitude=Decimal("37.700000"), longitude=Decimal("127.100000"),
        event_start_at=event_time + timedelta(days=7), event_end_at=event_time + timedelta(days=7),
    )
    missing = Post(**common)

    assert score_posts(source, near) > score_posts(source, far)
    assert score_posts(source, missing) > 0
