"""Verify LangGraph routing without a database or external model."""

from app.ai.schemas import AIDraftResponse
from app.ai.workflow import run_chat_workflow


def draft_with_missing_fields(*missing_fields: str) -> AIDraftResponse:
    return AIDraftResponse(
        post_type="LOST",
        title="에어팟 분실",
        description="에어팟을 잃어버렸습니다.",
        item_name="에어팟",
        category_id=1,
        category_code="ELECTRONICS",
        location_text=None if "location" in missing_fields else "삼성학술정보관",
        latitude=None,
        longitude=None,
        event_start_at=None,
        event_end_at=None,
        keywords=["에어팟"],
        missing_fields=list(missing_fields),
        warnings=[],
    )


def test_chat_workflow_routes_to_highest_priority_missing_field() -> None:
    received_conversations: list[str] = []

    def generate(conversation: str) -> AIDraftResponse:
        received_conversations.append(conversation)
        return draft_with_missing_fields("event_time", "location")

    state = run_chat_workflow(
        post_type="LOST",
        user_messages=["에어팟을 잃어버렸어요.", "어제였어요."],
        draft_generator=generate,
    )

    assert state["status"] == "NEEDS_INPUT"
    assert state["missing_field"] == "location"
    assert "어디" in state["assistant_message"]
    assert "사용자 1번째 입력: 에어팟을 잃어버렸어요." in received_conversations[0]
    assert "사용자 2번째 입력: 어제였어요." in received_conversations[0]


def test_chat_workflow_routes_complete_draft_to_review() -> None:
    state = run_chat_workflow(
        post_type="LOST",
        user_messages=["어제 삼성학술정보관에서 에어팟을 잃어버렸어요."],
        draft_generator=lambda _: draft_with_missing_fields(),
    )

    assert state["status"] == "READY"
    assert state["missing_field"] is None
    assert "초안" in state["assistant_message"]
