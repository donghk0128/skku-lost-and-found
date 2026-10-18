"""Tests for the standalone structured draft contract."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.schemas import PostDraft, strict_json_schema


def valid_draft() -> dict:
    return {
        "title": "에어팟 분실",
        "description": "검은색 케이스입니다.",
        "item_name": "에어팟",
        "category_code": "ELECTRONICS",
        "location_text": "학생회관",
        "event_start_at": datetime(2026, 10, 18, 12, tzinfo=timezone.utc),
        "event_end_at": datetime(2026, 10, 18, 13, tzinfo=timezone.utc),
        "keywords": ["검은색", "검은색", "케이스"],
        "missing_fields": [],
        "warnings": [],
    }


def test_draft_deduplicates_keywords() -> None:
    draft = PostDraft(**valid_draft())
    assert draft.keywords == ["검은색", "케이스"]


def test_draft_requires_time_pair() -> None:
    payload = valid_draft()
    payload["event_end_at"] = None
    with pytest.raises(ValidationError):
        PostDraft(**payload)


def test_strict_schema_requires_every_property() -> None:
    schema = strict_json_schema()
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False
