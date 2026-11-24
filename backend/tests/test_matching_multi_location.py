"""Possible post locations contribute the nearest available coordinate pair."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.matching.ranking import rank_candidates
from app.matching.scoring import LOCATION_WEIGHT, rule_signals
from app.posts.model import Post, PostLocation
from app.users.model import User  # noqa: F401 - register Post.author relationship


def post(kind: str, locations: list[tuple[str | None, float | None, float | None]]) -> Post:
    when = datetime(2026, 11, 18, tzinfo=timezone.utc)
    result = Post(
        id=uuid4(), post_type=kind, title="지갑", description="검은 지갑",
        category_id=1, event_start_at=when, event_end_at=when, created_at=when,
    )
    for position, (text, latitude, longitude) in enumerate(locations):
        result.locations.append(PostLocation(
            position=position, location_text=text,
            latitude=Decimal(str(latitude)) if latitude is not None else None,
            longitude=Decimal(str(longitude)) if longitude is not None else None,
        ))
    if locations:
        result.location_text = result.locations[0].location_text
        result.latitude = result.locations[0].latitude
        result.longitude = result.locations[0].longitude
    return result


def test_secondary_pins_can_be_the_nearest_pair_on_both_posts() -> None:
    source = post("LOST", [("먼 곳", 37.0, 127.0), ("가까운 곳", 37.5, 127.5)])
    candidate = post("FOUND", [("다른 먼 곳", 38.0, 128.0), ("가까운 곳", 37.5, 127.5)])
    far_candidate = post("FOUND", [("먼 곳", 38.0, 128.0)])

    signals = rule_signals(source, candidate)
    assert signals.distance_km == pytest.approx(0.0)
    assert signals.location == pytest.approx(1.0)
    assert rule_signals(candidate, source).distance_km == pytest.approx(0.0)
    ranked = rank_candidates(source, [candidate], {candidate.id: 0.8})[0]
    assert "NEARBY_LOCATION" in ranked.reasons
    assert ranked.signals.distance_km == pytest.approx(0.0)
    assert [item.post.id for item in rank_candidates(
        source, [far_candidate, candidate], {candidate.id: 0.8, far_candidate.id: 0.8},
    )] == [candidate.id, far_candidate.id]


def test_text_only_first_location_does_not_hide_a_later_pin() -> None:
    source = post("LOST", [("건물 이름만", None, None), (None, 37.5, 127.5)])
    candidate = post("FOUND", [("가까운 곳", 37.5, 127.5)])

    assert source.latitude is None
    signals = rule_signals(source, candidate)
    assert signals.distance_km == pytest.approx(0.0)
    assert signals.ranking_score == pytest.approx(signals.score)


def test_text_only_locations_keep_v4_missing_coordinate_reweighting() -> None:
    source = post("LOST", [("장소만", None, None)])
    candidate = post("FOUND", [("핀", 37.5, 127.5)])

    signals = rule_signals(source, candidate)
    assert signals.distance_km is None
    assert signals.location == 0.0
    assert signals.ranking_score == pytest.approx(signals.score / (1 - LOCATION_WEIGHT))
    assert "NEARBY_LOCATION" not in rank_candidates(source, [candidate], {})[0].reasons


def test_legacy_scalar_coordinates_work_without_location_rows() -> None:
    source = post("LOST", [])
    candidate = post("FOUND", [])
    source.latitude = candidate.latitude = Decimal("37.500000")
    source.longitude = candidate.longitude = Decimal("127.500000")

    assert rule_signals(source, candidate).distance_km == pytest.approx(0.0)
