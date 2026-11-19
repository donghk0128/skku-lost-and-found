from datetime import date
from types import SimpleNamespace

from app.ai.core.providers import FakeProvider
from app.ai.core.schemas import PostDraft
from app.ai.schemas import AIChatMessage, AIChatRequest
from app.ai.service import AIDraftService
from app.posts.repository import PostRepository


def test_chat_waits_for_valid_multiple_location_selection(monkeypatch) -> None:
    monkeypatch.setattr(
        PostRepository,
        "get_category_by_code",
        lambda _db, code: SimpleNamespace(id=1, code=code),
    )
    provider = FakeProvider(
        PostDraft(
            title="학생회관 분실물",
            description="학관에서 물건을 잃어버렸습니다.",
            item_name="지갑",
            category_code="WALLET",
            event_start_date=date(2026, 11, 19),
            event_end_date=date(2026, 11, 19),
            time_precision="DATE_ONLY",
            missing_fields=["location"],
        )
    )
    messages = [AIChatMessage(content="학관에서 오늘 지갑을 잃어버렸어요")]

    pending = AIDraftService.continue_chat(
        None,
        AIChatRequest(post_type="LOST", messages=messages),
        provider,
    )

    assert pending.pending_field == "location_selection"
    assert [option.id for option in pending.draft.location_options] == [
        "hssc_student_center",
        "nsc_student_center",
    ]
    assert [option.label for option in pending.draft.location_options] == [
        "인사캠 학생회관",
        "자과캠 학생회관",
    ]
    assert pending.draft.location_text is None

    selected = AIDraftService.continue_chat(
        None,
        AIChatRequest(
            post_type="LOST",
            messages=messages,
            draft=pending.draft,
            pending_field=pending.pending_field,
            selected_location_ids=["hssc_student_center", "nsc_student_center"],
        ),
        provider,
    )

    assert selected.status == "READY"
    assert selected.selected_location_ids == [
        "hssc_student_center",
        "nsc_student_center",
    ]
    assert selected.draft.location_text == "인사캠 학생회관, 자과캠 학생회관"
