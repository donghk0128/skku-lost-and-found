"""Exercise post routes through FastAPI using an isolated in-memory database."""

import os
import base64
from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal
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
from app.posts.model import Category, Post, PostImage
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


def create_author(engine: Engine, email: str = "api-post-author@g.skku.edu") -> UUID:
    with Session(engine) as db:
        author = User(
            email=email,
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


def test_list_posts_filters_paginates_and_hides_deleted(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    author_id = create_author(engine)
    headers = {"Authorization": f"Bearer {create_access_token(author_id)}"}
    post_ids = []

    for title, post_type in [
        ("오래된 분실물", "LOST"),
        ("습득물", "FOUND"),
        ("새 분실물", "LOST"),
        ("삭제된 분실물", "LOST"),
    ]:
        response = client.post(
            "/api/v1/posts",
            headers=headers,
            json={**post_payload(), "title": title, "post_type": post_type},
        )
        assert response.status_code == 201
        post_ids.append(response.json()["id"])

    with Session(engine) as db:
        for index, post_id in enumerate(post_ids):
            post = db.get(Post, UUID(post_id))
            assert post is not None
            post.created_at = datetime(2026, 1, index + 1, tzinfo=timezone.utc)
            if index == 3:
                post.deleted_at = datetime.now(timezone.utc)
        db.commit()

    all_posts = client.get("/api/v1/posts")
    assert all_posts.status_code == 200
    assert all_posts.json()["total"] == 3
    assert all_posts.json()["limit"] == 20
    assert all_posts.json()["offset"] == 0
    assert [item["id"] for item in all_posts.json()["items"]] == [post_ids[2], post_ids[1], post_ids[0]]

    second_lost_post = client.get("/api/v1/posts?post_type=LOST&limit=1&offset=1")
    assert second_lost_post.status_code == 200
    assert second_lost_post.json()["total"] == 2
    assert [item["id"] for item in second_lost_post.json()["items"]] == [post_ids[0]]

    assert client.get("/api/v1/posts?post_type=OTHER").status_code == 422
    assert client.get("/api/v1/posts?limit=0").status_code == 422
    assert client.get("/api/v1/posts?offset=-1").status_code == 422


def test_only_author_can_update_post(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    author_id = create_author(engine)
    other_id = create_author(engine, "other-post-author@g.skku.edu")
    author_headers = {"Authorization": f"Bearer {create_access_token(author_id)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other_id)}"}
    created = client.post("/api/v1/posts", headers=author_headers, json=post_payload())
    assert created.status_code == 201
    post_id = created.json()["id"]

    path = f"/api/v1/posts/{post_id}"
    assert client.patch(path, json={"title": "새 제목"}).status_code == 401
    forbidden = client.patch(path, headers=other_headers, json={"title": "새 제목"})
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "post_forbidden"

    for invalid_body in [{}, {"title": "   "}, {"title": None}, {"author_id": str(other_id)}]:
        assert client.patch(path, headers=author_headers, json=invalid_body).status_code == 422

    updated = client.patch(path, headers=author_headers, json={"title": "  새 제목  "})
    assert updated.status_code == 200
    assert updated.json()["title"] == "새 제목"
    assert updated.json()["description"] == "검은색 케이스"
    assert updated.json()["author_id"] == str(author_id)

    with Session(engine) as db:
        saved = db.get(Post, UUID(post_id))
        assert saved is not None
        assert saved.title == "새 제목"
        assert saved.description == "검은색 케이스"


def test_only_author_can_soft_delete_post(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    author_id = create_author(engine)
    other_id = create_author(engine, "other-post-author@g.skku.edu")
    author_headers = {"Authorization": f"Bearer {create_access_token(author_id)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other_id)}"}
    created = client.post("/api/v1/posts", headers=author_headers, json=post_payload())
    assert created.status_code == 201
    post_id = created.json()["id"]

    path = f"/api/v1/posts/{post_id}"
    assert client.delete(path).status_code == 401
    assert client.delete(path, headers=other_headers).status_code == 403
    deleted = client.delete(path, headers=author_headers)
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(path).status_code == 404
    assert client.get("/api/v1/posts").json()["total"] == 0
    assert client.delete(path, headers=author_headers).status_code == 404
    assert client.patch(path, headers=author_headers, json={"title": "수정"}).status_code == 404

    with Session(engine) as db:
        saved = db.get(Post, UUID(post_id))
        assert saved is not None
        assert saved.deleted_at is not None


def test_create_and_read_optional_post_details(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    author_id = create_author(engine)
    headers = {"Authorization": f"Bearer {create_access_token(author_id)}"}
    payload = {
        **post_payload(),
        "item_name": "  에어팟  ",
        "location_text": "  학생회관  ",
        "latitude": "37.588001",
        "longitude": "126.993000",
        "event_start_at": "2026-10-15T00:00:00Z",
        "event_end_at": "2026-10-15T01:00:00Z",
    }

    created = client.post("/api/v1/posts", headers=headers, json=payload)
    assert created.status_code == 201
    data = created.json()
    assert data["item_name"] == "에어팟"
    assert data["location_text"] == "학생회관"
    assert data["latitude"] == 37.588001
    assert data["longitude"] == 126.993
    assert data["event_start_at"].startswith("2026-10-15T00:00:00")
    assert data["event_end_at"].startswith("2026-10-15T01:00:00")
    assert client.get(f"/api/v1/posts/{data['id']}").json() == data

    with Session(engine) as db:
        saved = db.get(Post, UUID(data["id"]))
        assert saved is not None
        assert saved.latitude == Decimal("37.588001")
        assert saved.longitude == Decimal("126.993000")


def test_optional_post_details_validate_pairs_and_can_be_cleared(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    author_id = create_author(engine)
    headers = {"Authorization": f"Bearer {create_access_token(author_id)}"}
    invalid_details = [
        {"latitude": "37.588001"},
        {"latitude": "91", "longitude": "126.993000"},
        {"event_start_at": "2026-10-15T00:00:00Z"},
        {"event_start_at": "2026-10-15T02:00:00Z", "event_end_at": "2026-10-15T01:00:00Z"},
        {"event_start_at": "2026-10-15T00:00:00", "event_end_at": "2026-10-15T01:00:00"},
        {"item_name": "   "},
    ]
    for details in invalid_details:
        response = client.post("/api/v1/posts", headers=headers, json={**post_payload(), **details})
        assert response.status_code == 422

    created = client.post(
        "/api/v1/posts",
        headers=headers,
        json={
            **post_payload(),
            "location_text": "학생회관",
            "latitude": "37.588001",
            "longitude": "126.993000",
            "event_start_at": "2026-10-15T00:00:00Z",
            "event_end_at": "2026-10-15T01:00:00Z",
        },
    )
    assert created.status_code == 201
    path = f"/api/v1/posts/{created.json()['id']}"

    assert client.patch(path, headers=headers, json={"latitude": "37.6"}).status_code == 422
    cleared = client.patch(
        path,
        headers=headers,
        json={
            "location_text": None,
            "latitude": None,
            "longitude": None,
            "event_start_at": None,
            "event_end_at": None,
        },
    )
    assert cleared.status_code == 200
    for field in ("location_text", "latitude", "longitude", "event_start_at", "event_end_at"):
        assert cleared.json()[field] is None


def test_category_list_selection_filter_and_clear(api_client: tuple[TestClient, Engine]) -> None:
    client, engine = api_client
    with Session(engine) as db:
        db.add_all([
            Category(id=1, code="ELECTRONICS", name="전자기기"),
            Category(id=2, code="BAG", name="가방"),
        ])
        db.commit()

    categories_response = client.get("/api/v1/categories")
    assert categories_response.status_code == 200
    categories = categories_response.json()
    assert [item["code"] for item in categories] == ["ELECTRONICS", "BAG"]
    electronics_id, bag_id = [item["id"] for item in categories]

    author_id = create_author(engine)
    headers = {"Authorization": f"Bearer {create_access_token(author_id)}"}
    created = client.post(
        "/api/v1/posts",
        headers=headers,
        json={**post_payload(), "category_id": electronics_id},
    )
    assert created.status_code == 201
    assert created.json()["category_id"] == electronics_id
    assert client.get(f"/api/v1/posts?category_id={electronics_id}").json()["total"] == 1
    assert client.get(f"/api/v1/posts?category_id={bag_id}").json()["total"] == 0
    assert client.get("/api/v1/posts?category_id=0").status_code == 422

    missing_category = client.post(
        "/api/v1/posts",
        headers=headers,
        json={**post_payload(), "category_id": 999},
    )
    assert missing_category.status_code == 422
    assert missing_category.json()["error"]["code"] == "category_not_found"

    path = f"/api/v1/posts/{created.json()['id']}"
    invalid_update = client.patch(path, headers=headers, json={"category_id": 999})
    assert invalid_update.status_code == 422
    changed = client.patch(path, headers=headers, json={"category_id": bag_id})
    assert changed.status_code == 200
    assert changed.json()["category_id"] == bag_id
    cleared = client.patch(path, headers=headers, json={"category_id": None})
    assert cleared.status_code == 200
    assert cleared.json()["category_id"] is None


def test_post_image_upload_list_and_read_require_post_ownership(
    api_client: tuple[TestClient, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, engine = api_client
    author_id = create_author(engine)
    other_id = create_author(engine, "image-other@g.skku.edu")
    headers = {"Authorization": f"Bearer {create_access_token(author_id)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other_id)}"}
    created = client.post("/api/v1/posts", headers=headers, json=post_payload())
    assert created.status_code == 201
    post_id = created.json()["id"]
    path = f"/api/v1/posts/{post_id}/images"
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l3sAAAAASUVORK5CYII="
    )

    class FakeStorage:
        files: dict[str, bytes] = {}

        def upload(self, key: str, content: bytes, content_type: str) -> None:
            self.files[key] = content

        def download(self, key: str) -> bytes:
            return self.files[key]

        def delete(self, key: str) -> None:
            self.files.pop(key, None)

    storage = FakeStorage()
    monkeypatch.setattr("app.posts.service.get_post_image_storage", lambda: storage)
    file = {"file": ("tiny.png", image_bytes, "image/png")}
    assert client.post(path, files=file).status_code == 401
    assert client.post(path, headers=other_headers, files=file).status_code == 403
    assert client.post(path, headers=headers, files={"file": ("fake.png", b"abc", "image/png")}).status_code == 422
    assert client.post(path, headers=headers, files={"file": ("tiny.txt", image_bytes, "text/plain")}).status_code == 422
    assert client.post(path, headers=headers, files={"file": ("big.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")}).status_code == 422

    uploaded = client.post(path, headers=headers, files=file)
    assert uploaded.status_code == 201
    image = uploaded.json()
    assert image["post_id"] == post_id
    assert image["content_type"] == "image/png"
    assert image["position"] == 0
    assert "storage_key" not in image
    assert client.get(path).json() == [image]
    content = client.get(image["content_url"])
    assert content.status_code == 200
    assert content.headers["content-type"] == "image/png"
    assert content.content == image_bytes

    with Session(engine) as db:
        saved = db.get(PostImage, UUID(image["id"]))
        assert saved is not None
        assert saved.storage_key in storage.files

    assert client.get(f"{path}/{uuid4()}/content").status_code == 404
    assert client.delete(f"/api/v1/posts/{post_id}", headers=headers).status_code == 204
    assert client.get(path).status_code == 404
    assert client.get(image["content_url"]).status_code == 404
