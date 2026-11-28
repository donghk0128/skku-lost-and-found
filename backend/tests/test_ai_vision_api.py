import asyncio
import json
from io import BytesIO

import pytest
from starlette.datastructures import Headers, UploadFile

from app.ai.core.providers import FakeProvider, ProviderError
from app.ai.core.schemas import PostDraft
from app.ai.core.vision_providers import VisionProvider
from app.ai.core.vision_schemas import ImageAttributes, VisionResult, VisionUsage
from app.ai.router import continue_post_draft_chat_with_images
from app.ai.schemas import AIChatRequest, AIRequiredFields, LocationOption
from app.ai.service import AIDraftService
from app.core.errors import ApiError


class FakeVisionProvider(VisionProvider):
    locale = None

    def analyze(self, image: bytes, mime_type: str, locale: str) -> VisionResult:
        self.locale = locale
        return VisionResult(
            attributes=ImageAttributes(
                item_name="wireless earbuds",
                category_code="ELECTRONICS",
                colors=["black"],
                visible_text=["Samsung Library", "2026-11-20 14:00"],
                confidence=0.9,
            ),
            usage=VisionUsage(input_tokens=1, output_tokens=1, duration_seconds=0.1),
            provider="fake",
            model="fake",
        )


class RecordingProvider(FakeProvider):
    def __init__(self, draft):
        super().__init__(draft)
        self.natural_language = ""
        self.extract_calls = 0

    def extract_required_fields(self, request):
        self.extract_calls += 1
        self.natural_language = request.natural_language
        return super().extract_required_fields(request)


class FailingVisionProvider(VisionProvider):
    def analyze(self, image: bytes, mime_type: str, locale: str) -> VisionResult:
        raise ProviderError("unavailable")


def test_multipart_chat_returns_reusable_attributes_without_text_context_leak():
    payload = json.dumps({
        "post_type": "LOST",
        "locale": "en",
        "messages": [{"role": "user", "content": "Attached an image"}],
    })
    image = UploadFile(
        BytesIO(b"\x89PNG\r\n\x1a\npayload"),
        filename="item.png",
        headers=Headers({"content-type": "image/png"}),
    )
    draft_provider = RecordingProvider(PostDraft(
        title="Black wireless earbuds",
        description="Black wireless earbuds.",
        item_name="wireless earbuds",
        category_code="ELECTRONICS",
        missing_fields=[],
    ))

    vision_provider = FakeVisionProvider()
    response = asyncio.run(continue_post_draft_chat_with_images(
        payload=payload,
        images=[image],
        _=None,
        db=None,
        provider=draft_provider,
        vision_provider=vision_provider,
    ))

    assert response.images_analyzed is True
    assert vision_provider.locale == "en"
    assert response.image_attributes is not None
    assert response.image_attributes.visible_text == [
        "Samsung Library",
        "2026-11-20 14:00",
    ]
    assert response.required_fields.item_name == "wireless earbuds"
    assert response.required_fields.location_text is None
    assert response.required_fields.event_start_at is None
    assert response.required_fields.event_end_at is None
    assert response.pending_field == "location"
    assert "event_time" in response.required_fields.missing_fields
    assert draft_provider.natural_language == "Attached an image"


def test_multipart_chat_maps_vision_failure_before_text_provider_call():
    payload = json.dumps({
        "post_type": "LOST",
        "locale": "en",
        "messages": [{"role": "user", "content": "Attached an image"}],
    })
    image = UploadFile(
        BytesIO(b"\x89PNG\r\n\x1a\npayload"),
        filename="item.png",
        headers=Headers({"content-type": "image/png"}),
    )
    draft_provider = RecordingProvider(PostDraft(
        title="Unknown item",
        description="An item was attached.",
        item_name=None,
        category_code="OTHER",
        missing_fields=["item_name", "location", "event_time"],
    ))

    with pytest.raises(ApiError) as caught:
        asyncio.run(continue_post_draft_chat_with_images(
            payload=payload,
            images=[image],
            _=None,
            db=None,
            provider=draft_provider,
            vision_provider=FailingVisionProvider(),
        ))

    assert caught.value.status_code == 503
    assert caught.value.code == "ai_unavailable"
    assert draft_provider.extract_calls == 0


def test_confirmed_location_skips_stale_location_selection():
    provider = FakeProvider(PostDraft(
        title="Wallet",
        description="Black wallet.",
        item_name="wallet",
        category_code="OTHER",
        missing_fields=["location", "event_time"],
    ))
    request = AIChatRequest(
        post_type="LOST",
        locale="en",
        messages=[{"role": "user", "content": "I confirmed it on the map."}],
        required_fields=AIRequiredFields(
            item_name="wallet",
            location_options=[
                LocationOption(id="a", name="Library", label="Library"),
                LocationOption(id="b", name="Student Center", label="Student Center"),
            ],
            missing_fields=["location", "event_time"],
        ),
        pending_field="location_selection",
        confirmed_location={
            "text": "Engineering Building 2",
            "latitude": "37.293000",
            "longitude": "126.975000",
        },
    )

    response = AIDraftService.continue_chat(None, request, provider)

    assert response.required_fields.location_text == "Engineering Building 2"
    assert response.required_fields.location_options == []
    assert "location" not in response.required_fields.missing_fields
    assert response.pending_field == "event_time"


def test_confirmed_primary_pin_preserves_selected_locations():
    provider = FakeProvider(PostDraft(
        title="Wallet",
        description="Black wallet.",
        item_name="wallet",
        category_code="OTHER",
        missing_fields=["event_time"],
    ))
    options = [
        LocationOption(id="general", name="기초학문관", label="기초학문관"),
        LocationOption(id="life", name="생명공학관", label="생명공학관"),
    ]
    request = AIChatRequest(
        post_type="LOST",
        messages=[{"role": "user", "content": "두 건물 사이에서 잃어버렸어요."}],
        required_fields=AIRequiredFields(
            item_name="지갑",
            location_text="기초학문관, 생명공학관",
            location_candidates=[option.name for option in options],
            location_options=options,
            selected_location_ids=[option.id for option in options],
            missing_fields=["event_time"],
        ),
        pending_field="event_time",
        selected_location_ids=[option.id for option in options],
        confirmed_location={
            "text": "기초학문관",
            "latitude": "37.293000",
            "longitude": "126.975000",
        },
    )

    response = AIDraftService.continue_chat(None, request, provider)

    assert response.required_fields.location_text == "기초학문관, 생명공학관"
    assert response.required_fields.selected_location_ids == ["general", "life"]
    assert response.pending_field == "event_time"
