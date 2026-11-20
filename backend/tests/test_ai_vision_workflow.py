import pytest

from app.ai.core.providers import ProviderError
from app.ai.core.vision_schemas import (
    ImageAttributes,
    ImageInput,
    MergedImageAttributes,
    VisionResult,
    VisionUsage,
)
from app.ai.schemas import AIRequiredFields, LocationOption
from app.ai.workflow import _image_field_warnings, run_chat_workflow


def merged_attributes(*, visible_text: list[str] | None = None) -> MergedImageAttributes:
    attributes = ImageAttributes(
        item_name="wireless earbuds",
        category_code="ELECTRONICS",
        colors=["black"],
        visible_text=visible_text or [],
        confidence=0.9,
    )
    usage = VisionUsage(input_tokens=1, output_tokens=1, duration_seconds=0.1)
    return MergedImageAttributes(
        item_name=attributes.item_name,
        category_code=attributes.category_code,
        colors=attributes.colors,
        confidence=attributes.confidence,
        image_results=[VisionResult(attributes=attributes, usage=usage, provider="fake", model="fake")],
        usage=usage,
    )


def fields(item_name=None) -> AIRequiredFields:
    missing = ["location", "event_time"]
    if item_name is None:
        missing.insert(0, "item_name")
    return AIRequiredFields(item_name=item_name, missing_fields=missing)


def test_image_fills_item_without_entering_text_extraction_context():
    conversations = []

    def extract(conversation, _matches):
        conversations.append(conversation)
        return fields()

    state = run_chat_workflow(
        post_type="LOST",
        user_messages=["사진을 첨부했어요"],
        field_extractor=extract,
        draft_generator=lambda *_: None,
        previous_required_fields=fields(),
        pending_field="item_name",
        images=[ImageInput(content=b"\xff\xd8\xffpayload", mime_type="image/jpeg")],
        image_analyzer=lambda _images: merged_attributes(
            visible_text=["Samsung Library", "2026-11-20 14:00"]
        ),
    )

    assert state["images_analyzed"] is True
    assert state["fields"].item_name == "wireless earbuds"
    assert state["fields"].location_text is None
    assert state["fields"].event_start_at is None
    assert state["fields"].event_end_at is None
    assert state["pending_field"] == "location"
    assert conversations == ["사진을 첨부했어요"]


def test_no_images_preserves_collect_route():
    extract_calls = 0

    def extract(_conversation, _matches):
        nonlocal extract_calls
        extract_calls += 1
        return fields()

    state = run_chat_workflow(
        post_type="LOST",
        user_messages=["지갑"],
        field_extractor=extract,
        draft_generator=lambda *_: None,
        previous_required_fields=fields(),
        pending_field="item_name",
    )

    assert extract_calls == 0
    assert state["fields"].item_name == "지갑"
    assert state["pending_field"] == "location"


def test_image_failure_stops_before_text_provider_call():
    def fail(_images):
        raise ProviderError("unavailable")

    extracted = []

    def extract(conversation, _matches):
        extracted.append(conversation)
        return fields()

    with pytest.raises(ProviderError, match="unavailable"):
        run_chat_workflow(
            post_type="LOST",
            user_messages=["사진을 첨부했어요"],
            field_extractor=extract,
            draft_generator=lambda *_: None,
            previous_required_fields=fields(),
            pending_field="item_name",
            images=[ImageInput(content=b"\xff\xd8\xffpayload", mime_type="image/jpeg")],
            image_analyzer=fail,
        )

    assert extracted == []


def test_image_upload_preserves_selected_locations():
    options = [
        LocationOption(id="library", name="Samsung Library", label="Samsung Library"),
        LocationOption(id="hall", name="Student Hall", label="Student Hall"),
    ]
    previous = AIRequiredFields(
        item_name="wireless earbuds",
        location_options=options,
        missing_fields=["location", "event_time"],
    )
    extract_calls = 0

    def extract(*_args):
        nonlocal extract_calls
        extract_calls += 1
        return fields()

    state = run_chat_workflow(
        post_type="LOST",
        user_messages=["사진을 추가했어요"],
        field_extractor=extract,
        draft_generator=lambda *_: None,
        previous_required_fields=previous,
        pending_field="location_selection",
        selected_location_ids=["library"],
        images=[ImageInput(content=b"\xff\xd8\xffpayload", mime_type="image/jpeg")],
        image_analyzer=lambda _images: merged_attributes(),
    )

    assert extract_calls == 0
    assert state["fields"].location_text == "Samsung Library"
    assert state["fields"].selected_location_ids == ["library"]
    assert state["pending_field"] == "event_time"


def test_image_cannot_skip_missing_event_time():
    incomplete = AIRequiredFields(
        item_name="wireless earbuds",
        location_text="Samsung Library",
        missing_fields=[],
    )

    state = run_chat_workflow(
        post_type="LOST",
        user_messages=["사진을 첨부했어요"],
        field_extractor=lambda *_: incomplete,
        draft_generator=lambda *_: None,
        previous_required_fields=incomplete,
        pending_field="event_time",
        images=[ImageInput(content=b"\xff\xd8\xffpayload", mime_type="image/jpeg")],
        image_analyzer=lambda _images: merged_attributes(),
    )

    assert state["status"] == "NEEDS_INPUT"
    assert state["pending_field"] == "event_time"
    assert state["assistant_message"] == "분실 추정 시간은 언제인가요?"


def test_only_image_item_conflict_becomes_user_visible_warning():
    state = {
        "locale": "ko",
        "image_attributes": merged_attributes(),
        "previous_fields": AIRequiredFields(item_name="가방"),
    }

    assert _image_field_warnings(state, "BAG") == [
        "사진에서는 'wireless earbuds'(으)로 보이지만 입력된 물품은 '가방'입니다."
    ]

    state["previous_fields"] = AIRequiredFields(item_name="wireless earbuds")
    assert _image_field_warnings(state, "ELECTRONICS") == []
