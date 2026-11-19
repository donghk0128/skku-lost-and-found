import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough")

from app.matching.ranking import rank_candidates
from app.posts.model import Post


def test_reasons_follow_individual_signals() -> None:
    when = datetime(2026, 11, 18, 14, tzinfo=timezone.utc)
    source = Post(
        id=uuid4(), post_type="FOUND", title="검은 에어팟", description="도서관",
        category_id=1, latitude=Decimal("37.588000"), longitude=Decimal("126.993000"),
        event_start_at=when, event_end_at=when,
    )
    candidate = Post(
        id=uuid4(), post_type="LOST", title="무선 이어폰", description="도서관",
        category_id=1, latitude=Decimal("37.588100"), longitude=Decimal("126.993100"),
        event_start_at=when - timedelta(hours=1), event_end_at=when + timedelta(hours=1),
    )
    result = rank_candidates(source, [candidate], {candidate.id: 0.8})[0]
    assert result.reasons == ["NEARBY_LOCATION", "OVERLAPPING_TIME", "SAME_CATEGORY", "SIMILAR_MEANING"]


def test_missing_signals_do_not_claim_a_match() -> None:
    source = Post(id=uuid4(), post_type="FOUND", title="검은 에어팟", description="도서관")
    candidate = Post(id=uuid4(), post_type="LOST", title="지갑", description="학생회관")
    result = rank_candidates(source, [candidate], {})[0]
    assert result.reasons == []
    assert result.semantic_score is None
