"""Tests for deterministic baseline metrics."""

from datetime import datetime, timedelta, timezone

from evals.metrics import set_f1, time_match, token_f1


def test_token_f1_handles_equal_and_missing_values() -> None:
    assert token_f1("검은색 에어팟", "검은색 에어팟") == 1
    assert token_f1(None, None) == 1
    assert token_f1("에어팟", None) == 0


def test_set_f1_ignores_order() -> None:
    assert set_f1(["location", "event_time"], ["event_time", "location"]) == 1


def test_time_match_uses_fifteen_minute_tolerance() -> None:
    expected = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
    assert time_match(expected, expected + timedelta(minutes=15)) == 1
    assert time_match(expected, expected + timedelta(minutes=16)) == 0
