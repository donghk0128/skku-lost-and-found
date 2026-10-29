"""Tests for deterministic baseline metrics."""

from datetime import date

from evals.metrics import date_match, set_f1, token_f1


def test_token_f1_handles_equal_and_missing_values() -> None:
    assert token_f1("검은색 에어팟", "검은색 에어팟") == 1
    assert token_f1(None, None) == 1
    assert token_f1("에어팟", None) == 0


def test_set_f1_ignores_order() -> None:
    assert set_f1(["location", "event_time"], ["event_time", "location"]) == 1


def test_date_match_requires_same_calendar_date() -> None:
    expected = date(2026, 10, 18)
    assert date_match(expected, expected) == 1
    assert date_match(expected, date(2026, 10, 19)) == 0
