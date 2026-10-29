"""LangGraph workflow for text-only, human-reviewed post drafting."""

from collections.abc import Callable
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai.schemas import AIDraftResponse, PostType


ChatStatus = Literal["NEEDS_INPUT", "READY"]
DraftGenerator = Callable[[str], AIDraftResponse]


class ChatWorkflowState(TypedDict, total=False):
    """Serializable drafting state that can later accept RAG and image evidence."""

    post_type: PostType
    user_messages: list[str]
    draft: AIDraftResponse
    missing_field: str | None
    status: ChatStatus
    assistant_message: str


QUESTIONS = {
    "item_name": "어떤 물건인지 조금 더 구체적으로 알려주세요.",
    "location": "어디에서 있었던 일인가요? 건물이나 장소를 알려주세요.",
    "event_time": "언제 있었던 일인가요? 날짜와 대략적인 시간을 알려주세요.",
}
MISSING_FIELD_PRIORITY = tuple(QUESTIONS)
TRACE_TAGS = ["ai", "post-draft", "text-chat"]


def _conversation_text(messages: list[str]) -> str:
    return "\n".join(
        f"사용자 {index + 1}번째 입력: {message}"
        for index, message in enumerate(messages)
    )


def build_chat_workflow(draft_generator: DraftGenerator):
    """Compile the text drafting graph with an injected, testable model operation."""

    def extract_draft(state: ChatWorkflowState) -> ChatWorkflowState:
        draft = draft_generator(_conversation_text(state["user_messages"]))
        missing_field = next(
            (field for field in MISSING_FIELD_PRIORITY if field in draft.missing_fields),
            None,
        )
        return {"draft": draft, "missing_field": missing_field}

    def route_after_extraction(state: ChatWorkflowState) -> Literal["request_input", "prepare_review"]:
        return "request_input" if state.get("missing_field") else "prepare_review"

    def request_input(state: ChatWorkflowState) -> ChatWorkflowState:
        missing_field = state["missing_field"]
        if missing_field is None:
            raise ValueError("missing_field is required when requesting input")
        return {
            "status": "NEEDS_INPUT",
            "assistant_message": QUESTIONS[missing_field],
        }

    def prepare_review(_: ChatWorkflowState) -> ChatWorkflowState:
        return {
            "status": "READY",
            "assistant_message": "필요한 정보를 모두 확인했어요. 아래 초안을 확인해주세요.",
        }

    graph = StateGraph(ChatWorkflowState)
    graph.add_node("extract_draft", extract_draft)
    graph.add_node("request_input", request_input)
    graph.add_node("prepare_review", prepare_review)
    graph.add_edge(START, "extract_draft")
    graph.add_conditional_edges(
        "extract_draft",
        route_after_extraction,
        {
            "request_input": "request_input",
            "prepare_review": "prepare_review",
        },
    )
    graph.add_edge("request_input", END)
    graph.add_edge("prepare_review", END)
    return graph.compile(name="skku-post-draft-chat")


def run_chat_workflow(
    post_type: PostType,
    user_messages: list[str],
    draft_generator: DraftGenerator,
) -> ChatWorkflowState:
    """Run one stateless graph turn using the complete client-side conversation."""

    graph = build_chat_workflow(draft_generator)
    return graph.invoke(
        {
            "post_type": post_type,
            "user_messages": user_messages,
        },
        config={
            "run_name": "post-draft-chat-turn",
            "tags": TRACE_TAGS,
            "metadata": {
                "post_type": post_type,
                "message_count": len(user_messages),
            },
        },
    )
