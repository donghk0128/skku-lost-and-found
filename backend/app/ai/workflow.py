"""LangGraph workflow for text-only, human-reviewed post drafting."""

from collections.abc import Callable
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai.schemas import AIDraftResponse, PostType, RequiredDraftField
from app.integrations.ai.knowledge.location_retriever import LocationMatch, find_locations


ChatStatus = Literal["NEEDS_INPUT", "READY"]
DraftGenerator = Callable[[str, tuple[LocationMatch, ...]], AIDraftResponse]


class ChatWorkflowState(TypedDict, total=False):
    """Serializable drafting state that can later accept RAG and image evidence."""

    post_type: PostType
    user_messages: list[str]
    draft: AIDraftResponse
    previous_draft: AIDraftResponse
    pending_field: RequiredDraftField | None
    collected_fields: dict[RequiredDraftField, str]
    location_matches: tuple[LocationMatch, ...]
    status: ChatStatus
    assistant_message: str


QUESTIONS = {
    "item_name": "어떤 물건인지 조금 더 구체적으로 알려주세요.",
    "location": "어디에서 있었던 일인가요? 건물이나 장소를 알려주세요.",
    "event_time": "언제 있었던 일인가요? 알고 있는 날짜만 알려주세요.",
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

    def retrieve_location(state: ChatWorkflowState) -> ChatWorkflowState:
        latest_matches = find_locations(state["user_messages"][-1])
        matches = (
            latest_matches
            if len(latest_matches) == 1
            else find_locations(_conversation_text(state["user_messages"]))
        )
        return {"location_matches": matches}

    def extract_draft(state: ChatWorkflowState) -> ChatWorkflowState:
        draft = draft_generator(
            _conversation_text(state["user_messages"]),
            state.get("location_matches", ()),
        )
        pending_field = next(
            (field for field in MISSING_FIELD_PRIORITY if field in draft.missing_fields),
            None,
        )
        return {"draft": draft, "pending_field": pending_field}

    def route_at_start(state: ChatWorkflowState) -> Literal["collect_answer", "extract_draft"]:
        if state.get("previous_draft") is not None and state.get("pending_field") is not None:
            return "collect_answer"
        return "extract_draft"

    def collect_answer(state: ChatWorkflowState) -> ChatWorkflowState:
        pending_field = state["pending_field"]
        if pending_field is None:
            raise ValueError("pending_field is required when collecting an answer")
        collected_fields = dict(state.get("collected_fields", {}))
        collected_fields[pending_field] = state["user_messages"][-1]
        remaining_fields = [
            field
            for field in state["previous_draft"].missing_fields
            if field not in collected_fields
        ]
        draft = state["previous_draft"].model_copy(update={"missing_fields": remaining_fields})
        next_field = next(
            (field for field in MISSING_FIELD_PRIORITY if field in remaining_fields),
            None,
        )
        return {
            "draft": draft,
            "pending_field": next_field,
            "collected_fields": collected_fields,
        }

    def route_after_draft(state: ChatWorkflowState) -> Literal["request_input", "prepare_review"]:
        return "request_input" if state.get("pending_field") else "prepare_review"

    def route_after_collection(state: ChatWorkflowState) -> Literal["request_input", "extract_draft"]:
        return "request_input" if state.get("pending_field") else "extract_draft"

    def request_input(state: ChatWorkflowState) -> ChatWorkflowState:
        pending_field = state["pending_field"]
        if pending_field is None:
            raise ValueError("pending_field is required when requesting input")
        if pending_field == "location" and state["draft"].location_candidates:
            candidates = "\n".join(
                f"{index}. {candidate}"
                for index, candidate in enumerate(state["draft"].location_candidates, start=1)
            )
            assistant_message = f"여러 장소가 확인됐어요. 어느 장소인가요?\n{candidates}"
        else:
            assistant_message = QUESTIONS[pending_field]
        return {
            "status": "NEEDS_INPUT",
            "assistant_message": assistant_message,
        }

    def prepare_review(_: ChatWorkflowState) -> ChatWorkflowState:
        return {
            "status": "READY",
            "assistant_message": "필요한 정보를 모두 확인했어요. 아래 초안을 확인해주세요.",
        }

    graph = StateGraph(ChatWorkflowState)
    graph.add_node("retrieve_location", retrieve_location)
    graph.add_node("extract_draft", extract_draft)
    graph.add_node("collect_answer", collect_answer)
    graph.add_node("request_input", request_input)
    graph.add_node("prepare_review", prepare_review)
    graph.add_edge(START, "retrieve_location")
    graph.add_conditional_edges(
        "retrieve_location",
        route_at_start,
        {"collect_answer": "collect_answer", "extract_draft": "extract_draft"},
    )
    graph.add_conditional_edges(
        "extract_draft",
        route_after_draft,
        {
            "request_input": "request_input",
            "prepare_review": "prepare_review",
        },
    )
    graph.add_conditional_edges(
        "collect_answer",
        route_after_collection,
        {"request_input": "request_input", "extract_draft": "extract_draft"},
    )
    graph.add_edge("request_input", END)
    graph.add_edge("prepare_review", END)
    return graph.compile(name="skku-post-draft-chat")


def run_chat_workflow(
    post_type: PostType,
    user_messages: list[str],
    draft_generator: DraftGenerator,
    previous_draft: AIDraftResponse | None = None,
    pending_field: RequiredDraftField | None = None,
    collected_fields: dict[RequiredDraftField, str] | None = None,
) -> ChatWorkflowState:
    """Run one stateless graph turn using the complete client-side conversation."""

    graph = build_chat_workflow(draft_generator)
    return graph.invoke(
        {
            "post_type": post_type,
            "user_messages": user_messages,
            "previous_draft": previous_draft,
            "pending_field": pending_field,
            "collected_fields": collected_fields or {},
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
