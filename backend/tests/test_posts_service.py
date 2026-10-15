"""Post creation and visibility rules against an isolated SQLite database."""

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough")

from app.core.database import Base
from app.core.errors import ApiError
from app.posts.model import Post  # noqa: F401 - registers post tables
from app.posts.schemas import PostCreateRequest
from app.posts.service import PostService
from app.users.model import User


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_create_uses_authenticated_author_and_hides_deleted_post(db: Session) -> None:
    author = User(
        email="posts-author@g.skku.edu",
        password_hash="test-hash",
        nickname="작성자",
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(author)
    db.commit()
    db.refresh(author)

    request = PostCreateRequest(post_type="LOST", title="  에어팟 분실  ", description="  검은색 케이스  ")
    post = PostService.create(db, request, author)
    assert post.id is not None
    assert post.author_id == author.id
    assert post.title == "에어팟 분실"
    assert post.description == "검은색 케이스"
    assert post.status == "OPEN"
    assert post.creation_method == "MANUAL"
    assert PostService.get_visible_by_id(db, post.id).id == post.id

    post.deleted_at = datetime.now(timezone.utc)
    db.commit()
    with pytest.raises(ApiError) as error:
        PostService.get_visible_by_id(db, post.id)
    assert error.value.status_code == 404
    assert error.value.code == "post_not_found"


def test_request_rejects_forged_author_and_blank_title() -> None:
    with pytest.raises(ValidationError):
        PostCreateRequest.model_validate(
            {"post_type": "FOUND", "title": "지갑 발견", "description": "학생회관", "author_id": str(uuid4())}
        )

    with pytest.raises(ValidationError):
        PostCreateRequest(post_type="LOST", title="   ", description="설명")
