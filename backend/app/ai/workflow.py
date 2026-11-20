"""Collect required fields before generating a final AI post draft."""

from collections.abc import Callable
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai.knowledge.location_retriever import LocationMatch, find_locations
from app.ai.location_options import build_location_options
from app.ai.schemas import AIDraftResponse, AIRequiredFields, Locale, PendingDraftField, PostType
from app.ai.core.vision_schemas import ImageInput, MergedImageAttributes

FieldExtractor = Callable[[str, tuple[LocationMatch, ...]], AIRequiredFields]
DraftGenerator = Callable[
    [str, tuple[LocationMatch, ...], MergedImageAttributes | None],
    AIDraftResponse,
]
ImageAnalyzer = Callable[[list[ImageInput]], MergedImageAttributes]
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
    images: list[ImageInput]
    image_attributes: MergedImageAttributes | None
    images_analyzed: bool


def _text(messages: list[str]) -> str:
    return "\n".join(messages)


def _image_field_warnings(state: State, draft_category_code: str) -> list[str]:
    attributes = state.get("image_attributes")
    fields = state.get("fields") or state.get("previous_fields")
    if not attributes or not attributes.item_name or not fields or not fields.item_name:
        return []
    if (
        attributes.item_name.casefold().strip() == fields.item_name.casefold().strip()
        or attributes.category_code == draft_category_code
    ):
        return []
    if state["locale"] == "en":
        return [
            f"The photo appears to show '{attributes.item_name}', but the entered item is '{fields.item_name}'."
        ]
    return [
        f"사진에서는 '{attributes.item_name}'(으)로 보이지만 입력된 물품은 '{fields.item_name}'입니다."
    ]


def _pending(fields: AIRequiredFields) -> PendingDraftField | None:
    if len(fields.location_options) > 1 and not fields.selected_location_ids:
        return "location_selection"
    if not fields.item_name:
        return "item_name"
    if not fields.location_text:
        return "location"
    if fields.event_start_at is None or fields.event_end_at is None:
        return "event_time"
    return next((field for field in PRIORITY if field in fields.missing_fields), None)


def build_chat_workflow(
    extract_fields: FieldExtractor,
    generate_draft: DraftGenerator,
    image_analyzer: ImageAnalyzer | None = None,
):
    def analyze_images(state: State) -> State:
        images = state.get("images", [])
        if not images or image_analyzer is None:
            return {"images_analyzed": False}
        attributes = image_analyzer(images)
        return {
            "image_attributes": attributes,
            "images_analyzed": True,
        }

    def retrieve(state: State) -> State:
        query = state.get("location_correction") or (state["messages"][-1] if state["messages"] else "")
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
        attributes = state.get("image_attributes")
        if not fields.item_name and attributes and attributes.item_name:
            fields = fields.model_copy(update={
                "item_name": attributes.item_name,
                "missing_fields": [
                    field for field in fields.missing_fields if field != "item_name"
                ],
            })
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
            attributes = state.get("image_attributes")
            if attributes:
                extracted = extract_fields(_text(state["messages"]), state.get("matches", ()))
                item_name = extracted.item_name or attributes.item_name
                if not item_name:
                    return {"fields": fields, "pending_field": _pending(fields)}
            else:
                item_name = state["messages"][-1]
            updated = fields.model_copy(update={
                "item_name": item_name,
                "missing_fields": [field for field in fields.missing_fields if field != "item_name"],
            })
            return {"fields": updated, "pending_field": _pending(updated)}
        if pending == "event_time":
            extracted = extract_fields(_text(state["messages"]), state.get("matches", ()))
            missing = [field for field in extracted.missing_fields if field != "location"]
            item_name = extracted.item_name or fields.item_name
            if item_name:
                missing = [field for field in missing if field != "item_name"]
            if not fields.location_text:
                missing.append("location")
            updated = extracted.model_copy(update={
                "item_name": item_name,
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
        result = generate_draft(
            _text(state["messages"]),
            state.get("matches", ()),
            state.get("image_attributes"),
        )
        warnings = [
            *result.warnings,
            *_image_field_warnings(state, result.category_code),
        ]
        result = result.model_copy(
            update={"warnings": list(dict.fromkeys(warnings))}
        )
        message = "Please review the draft." if state["locale"] == "en" else "아래 초안을 확인해주세요."
        return {"draft": result, "status": "READY", "assistant_message": message}

    graph = StateGraph(State)
    graph.add_node("analyze_images", analyze_images)
    graph.add_node("retrieve", retrieve)
    graph.add_node("extract", extract)
    graph.add_node("collect", collect)
    graph.add_node("request", request)
    graph.add_node("draft", draft)
    graph.add_edge(START, "analyze_images")
    graph.add_edge("analyze_images", "retrieve")
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
    images: list[ImageInput] | None = None,
    image_analyzer: ImageAnalyzer | None = None,
    image_attributes: MergedImageAttributes | None = None,
) -> State:
    initial_state: State = {
        "locale": locale,
        "messages": user_messages,
        "previous_fields": previous_required_fields,
        "pending_field": pending_field,
        "selected_location_ids": selected_location_ids or [],
        "location_correction": location_correction,
        "images": images or [],
        "image_attributes": image_attributes,
    }
    if previous_required_fields is not None:
        initial_state["fields"] = previous_required_fields
    return build_chat_workflow(field_extractor, draft_generator, image_analyzer).invoke(initial_state)
