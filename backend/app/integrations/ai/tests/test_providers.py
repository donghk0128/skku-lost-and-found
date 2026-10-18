"""Tests for provider normalization without external model calls."""

from datetime import datetime, timezone

from core.providers import FakeProvider, OpenAIProvider
from core.schemas import DraftRequest, PostDraft


def test_fake_provider_returns_validated_result() -> None:
    draft = PostDraft(
        title="열쇠 습득",
        description="학생회관에서 열쇠를 주웠습니다.",
        item_name="열쇠",
        category_code="KEY",
        location_text="학생회관",
        event_start_at=None,
        event_end_at=None,
        keywords=["열쇠"],
        missing_fields=["event_time"],
        warnings=[],
    )
    request = DraftRequest(
        post_type="FOUND",
        natural_language="학생회관에서 열쇠를 주웠어요.",
        reference_time=datetime.now(timezone.utc),
    )
    result = FakeProvider(draft).generate(request)
    assert result.provider == "fake"
    assert result.draft.category_code == "KEY"


def test_openai_output_text_detects_refusal() -> None:
    from core.providers import ProviderError

    payload = {"output": [{"content": [{"type": "refusal", "refusal": "no"}]}]}
    try:
        OpenAIProvider._output_text(payload)
    except ProviderError as error:
        assert error.kind == "refused"
    else:
        raise AssertionError("Expected refusal to raise ProviderError")
