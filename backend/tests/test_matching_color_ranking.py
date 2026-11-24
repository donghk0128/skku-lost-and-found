"""Regression cases for explicit color conflicts and synonym item names."""

import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough")

from app.matching.ranking import ALGORITHM_VERSION, rank_candidates
from app.matching.model import RecommendationItem, RecommendationRun
from app.matching.scoring import LOCATION_WEIGHT, rule_signals, score_posts
from app.matching.service import MatchingService
from app.core.database import Base
from app.posts.model import Post
from app.users.model import User


def _post(post_type: str, title: str, item_name: str, description: str) -> Post:
    when = datetime(2026, 11, 18, 5, tzinfo=timezone.utc)
    return Post(
        id=uuid4(), post_type=post_type, title=title, item_name=item_name,
        description=description, category_id=1,
        event_start_at=when, event_end_at=when,
        created_at=when,
    )


def test_airpods_synonym_ranks_above_wrong_color_with_observed_semantic_scores() -> None:
    source = _post("FOUND", "삼성학술정보관 앞 검은 에어팟 습득", "에어팟", "검은 케이스에 초록색 스티커가 붙어 있습니다")
    correct = _post("LOST", "검은 에어팟을 잃어버렸습니다", "무선 이어폰", "케이스에 초록색 스티커가 있습니다")
    wrong_color = _post("LOST", "흰 에어팟 분실", "에어팟", "흰색 케이스이며 표시가 없습니다")

    ranked = rank_candidates(source, [wrong_color, correct], {correct.id: 0.9470, wrong_color.id: 0.8768})

    assert ALGORITHM_VERSION == "hybrid-v5"
    assert [item.post.id for item in ranked] == [correct.id, wrong_color.id]
    assert not ranked[0].signals.color_conflict
    assert ranked[1].signals.color_conflict
    assert ranked[0].score > ranked[1].score


def test_color_conflict_requires_explicit_different_colors_of_same_part() -> None:
    source = _post("FOUND", "검은 에어팟 습득", "에어팟", "검은 케이스에 초록 스티커")
    same = _post("LOST", "검정 이어폰 분실", "무선 이어폰", "검정색 케이스에 녹색 스티커")
    missing_color = _post("LOST", "무선 이어폰 분실", "이어폰", "케이스가 있습니다")
    different_part = _post("LOST", "검은 에어팟 분실", "에어팟", "흰색 스티커가 있습니다")
    conflicting = _post("LOST", "흰 에어팟 분실", "에어팟", "흰색 케이스에 초록 스티커")

    assert not rule_signals(source, same).color_conflict
    assert not rule_signals(source, missing_color).color_conflict
    assert rule_signals(source, different_part).color_conflict
    assert rule_signals(source, conflicting).color_conflict


def test_color_conflict_penalty_applies_without_embedding() -> None:
    source = _post("FOUND", "검은 지갑 습득", "지갑", "검은색 지갑")
    candidate = _post("LOST", "흰 지갑 분실", "지갑", "하얀색 지갑")
    ranked = rank_candidates(source, [candidate], {})[0]

    assert ranked.signals.color_conflict
    assert ranked.score == max(0.0, ranked.signals.ranking_score - 0.25)


def test_missing_coordinates_reweight_available_rule_signals() -> None:
    source = _post("FOUND", "검은 지갑 습득", "지갑", "학생증이 있습니다")
    source.latitude = Decimal("37.293900")
    source.longitude = Decimal("126.975100")
    candidate = _post("LOST", "지갑 분실", "지갑", "학생증이 들어 있습니다")

    signals = rule_signals(source, candidate)
    assert signals.distance_km is None
    assert signals.ranking_score == pytest.approx(signals.score / (1 - LOCATION_WEIGHT))
    assert score_posts(source, candidate) == pytest.approx(signals.ranking_score)
    ranked = rank_candidates(source, [candidate], {candidate.id: 0.8})[0]
    assert ranked.score == pytest.approx(0.5 * signals.ranking_score + 0.5 * 0.8)

    candidate.latitude = source.latitude
    candidate.longitude = source.longitude
    known_signals = rule_signals(source, candidate)
    assert known_signals.distance_km == pytest.approx(0.0)
    assert known_signals.ranking_score == pytest.approx(known_signals.score)


def test_new_version_keeps_old_run_and_records_color_conflict(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        author = User(
            email="evaluation@g.skku.edu", password_hash="test", nickname="evaluation",
            email_verified_at=datetime(2026, 11, 18, tzinfo=timezone.utc),
        )
        db.add(author)
        db.flush()
        source = _post("FOUND", "검은 에어팟 습득", "에어팟", "검은 케이스")
        candidate = _post("LOST", "흰 에어팟 분실", "에어팟", "흰 케이스")
        source.author_id = candidate.author_id = author.id
        db.add_all([source, candidate])
        db.commit()

        ranked = rank_candidates(source, [candidate], {candidate.id: 0.9})
        monkeypatch.setattr("app.matching.service.ALGORITHM_VERSION", "hybrid-v2")
        old_id = MatchingService._record_run(db, source, [candidate], ranked, {"post_type": "LOST"})
        monkeypatch.setattr("app.matching.service.ALGORITHM_VERSION", "hybrid-v5")
        new_id = MatchingService._record_run(db, source, [candidate], ranked, {"post_type": "LOST"})
        assert old_id != new_id
        assert MatchingService._record_run(db, source, [candidate], ranked, {"post_type": "LOST"}) == new_id
        assert [run.algorithm_version for run in db.scalars(select(RecommendationRun).order_by(RecommendationRun.algorithm_version))] == ["hybrid-v2", "hybrid-v5"]
        assert db.get(RecommendationItem, (new_id, candidate.id)).color_conflict
    engine.dispose()
