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
