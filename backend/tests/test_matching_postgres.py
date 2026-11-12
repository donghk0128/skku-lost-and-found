"""Optional pgvector integration check against a disposable migrated PostgreSQL DB."""

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.matching.model import PostEmbedding
from app.matching.repository import MatchingRepository
from app.posts.model import Post
from app.users.model import User


@pytest.mark.skipif(
    not os.getenv("TEST_PGVECTOR_DATABASE_URL"),
    reason="requires a disposable migrated PostgreSQL database",
)
def test_pgvector_cosine_similarity() -> None:
    engine = create_engine(os.environ["TEST_PGVECTOR_DATABASE_URL"])
    try:
        with Session(engine) as db:
            author = User(
                email="vector-check@g.skku.edu",
                password_hash="test-hash",
                nickname="검증자",
                email_verified_at=datetime.now(timezone.utc),
            )
            db.add(author)
            db.flush()
            posts = [
                Post(author_id=author.id, post_type=post_type, title=title, description="테스트")
                for post_type, title in [
                    ("LOST", "기준"),
                    ("FOUND", "비슷한 글"),
                    ("FOUND", "다른 글"),
                ]
            ]
            db.add_all(posts)
            db.flush()
            vectors = [
                [1.0, 0.0] + [0.0] * 766,
                [1.0, 0.0] + [0.0] * 766,
                [0.0, 1.0] + [0.0] * 766,
            ]
            db.add_all(
                PostEmbedding(post_id=post.id, model="test-model", content_hash="test", embedding=vector)
                for post, vector in zip(posts, vectors)
            )
            db.flush()

            scores = MatchingRepository.cosine_similarities(db, posts[0], [posts[1].id, posts[2].id])
            assert scores[posts[1].id] == pytest.approx(1.0)
            assert scores[posts[2].id] == pytest.approx(0.0)
            db.rollback()
    finally:
        engine.dispose()
