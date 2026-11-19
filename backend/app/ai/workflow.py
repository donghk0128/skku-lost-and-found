"""Collect required fields before generating a final AI post draft."""

from collections.abc import Callable
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai.knowledge.location_retriever import LocationMatch, find_locations
from app.ai.location_options import build_location_options
from app.ai.schemas import AIDraftResponse, AIRequiredFields, Locale, PendingDraftField, PostType

FieldExtractor = Callable[[str, tuple[LocationMatch, ...]], AIRequiredFields]
DraftGenerator = Callable[[str, tuple[LocationMatch, ...]], AIDraftResponse]
PRIORITY = ("item_name", "location", "event_time")
QUESTIONS = {
    "ko": {"item_name": "어떤 물건인지 알려주세요.", "location": "분실 추정 위치는 어디인가요?", "event_time": "분실 추정 시간은 언제인가요?"},
    "en": {"item_name": "What item was it?", "location": "Where did it happen?", "event_time": "When did it happen?"},
}


class State(TypedDict, total=False):
    locale: Locale
    messages: list[str]
    fields: AIRequiredFields
    previous_fields: AIRequiredFields
    draft: AIDraftResponse
    pending_field: PendingDraftField | None
    matches: tuple[LocationMatch, ...]
    selected_location_ids: list[str]
    location_correction: str | None
    status: Literal["NEEDS_INPUT", "READY"]
    assistant_message: str


def _text(messages: list[str]) -> str:
    return "\n".join(messages)


def _pending(fields: AIRequiredFields) -> PendingDraftField | None:
    if len(fields.location_options) > 1 and not fields.selected_location_ids:
        return "location_selection"
    return next((field for field in PRIORITY if field in fields.missing_fields), None)


def build_chat_workflow(extract_fields: FieldExtractor, generate_draft: DraftGenerator):
    def retrieve(state: State) -> State:
        query = state.get("location_correction") or state["messages"][-1]
        latest = find_locations(query, locale=state["locale"])
        matches = latest if state.get("location_correction") or len(latest) == 1 else find_locations(
            _text(state["messages"]), locale=state["locale"]
        )
        return {"matches": matches}

    def route_start(state: State) -> Literal["collect", "extract", "draft"]:
        previous = state.get("previous_fields")
        if previous and _pending(previous) is None:
            return "draft"
        return "collect" if previous else "extract"

    def extract(state: State) -> State:
        fields = extract_fields(_text(state["messages"]), state.get("matches", ()))
        return {"fields": fields, "pending_field": _pending(fields)}

    def collect(state: State) -> State:
        pending = state.get("pending_field")
        fields = state["previous_fields"]
        if pending == "location_selection":
            options = build_location_options(state.get("matches", ()), state["locale"]) if state.get("location_correction") else fields.location_options
            selected = state.get("selected_location_ids", [])
            if state.get("location_correction") and len(options) == 1:
                selected = [options[0].id]
            names = [option.name for option in options if option.id in selected]
            missing = [field for field in fields.missing_fields if field != "location"]
            if not names:
                missing.append("location")
            updated = fields.model_copy(update={
                "location_text": ", ".join(names) or None,
                "location_candidates": [option.name for option in options],
                "location_options": options,
                "selected_location_ids": selected,
                "missing_fields": missing,
            })
            return {"fields": updated, "pending_field": _pending(updated)}
        if pending == "item_name":
            updated = fields.model_copy(update={
                "item_name": state["messages"][-1],
                "missing_fields": [field for field in fields.missing_fields if field != "item_name"],
            })
            return {"fields": updated, "pending_field": _pending(updated)}
        if pending == "event_time":
            extracted = extract_fields(_text(state["messages"]), state.get("matches", ()))
            missing = [field for field in extracted.missing_fields if field != "location"]
            if not fields.location_text:
                missing.append("location")
            updated = extracted.model_copy(update={
                "location_text": fields.location_text,
                "location_candidates": fields.location_candidates,
                "location_options": fields.location_options,
                "selected_location_ids": fields.selected_location_ids,
                "missing_fields": list(dict.fromkeys(missing)),
            })
            return {"fields": updated, "pending_field": _pending(updated)}
        return extract(state)

    def route(state: State) -> Literal["request", "draft"]:
        return "request" if state.get("pending_field") else "draft"

    def request(state: State) -> State:
        pending = state["pending_field"]
        if pending == "location_selection":
            labels = "\n".join(f"{i}. {option.label}" for i, option in enumerate(state["fields"].location_options, 1))
            intro = "Select all applicable locations." if state["locale"] == "en" else "해당하는 장소를 모두 선택해 주세요."
            message = f"{intro}\n{labels}"
        else:
            message = QUESTIONS[state["locale"]][pending]
        return {"status": "NEEDS_INPUT", "assistant_message": message}

    def draft(state: State) -> State:
        result = generate_draft(_text(state["messages"]), state.get("matches", ()))
        message = "Please review the draft." if state["locale"] == "en" else "아래 초안을 확인해주세요."
        return {"draft": result, "status": "READY", "assistant_message": message}

    graph = StateGraph(State)
    graph.add_node("retrieve", retrieve)
    graph.add_node("extract", extract)
    graph.add_node("collect", collect)
    graph.add_node("request", request)
    graph.add_node("draft", draft)
    graph.add_edge(START, "retrieve")
    graph.add_conditional_edges("retrieve", route_start)
    graph.add_conditional_edges("extract", route)
    graph.add_conditional_edges("collect", route)
    graph.add_edge("request", END)
    graph.add_edge("draft", END)
    return graph.compile(name="skku-post-draft-chat")


def run_chat_workflow(
    post_type: PostType,
    user_messages: list[str],
    field_extractor: FieldExtractor,
    draft_generator: DraftGenerator,
    locale: Locale = "ko",
    previous_required_fields: AIRequiredFields | None = None,
    pending_field: PendingDraftField | None = None,
    selected_location_ids: list[str] | None = None,
    location_correction: str | None = None,
) -> State:
    initial_state: State = {
        "locale": locale,
        "messages": user_messages,
        "previous_fields": previous_required_fields,
        "pending_field": pending_field,
        "selected_location_ids": selected_location_ids or [],
        "location_correction": location_correction,
    }
    if previous_required_fields is not None:
        initial_state["fields"] = previous_required_fields
    return build_chat_workflow(field_extractor, draft_generator).invoke(initial_state)
