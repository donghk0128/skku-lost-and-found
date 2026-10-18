"""Tests for structured vision analysis without external API calls."""

import json

import httpx
import pytest

from core.providers import ProviderError
from core.vision_providers import OllamaVisionProvider, OpenAIVisionProvider
from core.vision_schemas import ImageAttributes, vision_json_schema


def valid_attributes() -> dict:
    return {
        "item_name": "지갑",
        "category_code": "WALLET",
        "colors": ["갈색", "갈색"],
        "materials": ["가죽"],
        "brand": None,
        "shape": "반지갑",
        "keywords": ["갈색", "가죽", "반지갑"],
        "visible_text": [],
        "confidence": 0.86,
        "warnings": ["브랜드는 확인할 수 없습니다."],
    }


def test_image_attributes_normalize_lists() -> None:
    attributes = ImageAttributes(**valid_attributes())
    assert attributes.colors == ["갈색"]
    assert attributes.brand is None


def test_vision_schema_is_strict() -> None:
    schema = vision_json_schema()
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False


def test_ollama_vision_payload_contains_base64_image(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        captured.update(kwargs["json"])
        return httpx.Response(
            200,
            json={
                "message": {"content": json.dumps(valid_attributes(), ensure_ascii=False)},
                "prompt_eval_count": 10,
                "eval_count": 20,
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = OllamaVisionProvider("moondream", "http://localhost:11434").analyze(b"image", "image/jpeg")
    assert captured["messages"][1]["images"] == ["aW1hZ2U="]
    assert captured["format"]["additionalProperties"] is False
    assert result.attributes.category_code == "WALLET"


def test_openai_vision_payload_uses_data_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        captured.update(kwargs["json"])
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [{"content": [{"type": "output_text", "text": json.dumps(valid_attributes())}]}],
                "usage": {"input_tokens": 30, "output_tokens": 20},
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = OpenAIVisionProvider("gpt-5.2", "test-key", "https://api.openai.com/v1").analyze(
        b"image", "image/png"
    )
    image_url = captured["input"][1]["content"][1]["image_url"]
    assert image_url == "data:image/png;base64,aW1hZ2U="
    assert captured["store"] is False
    assert result.usage.input_tokens == 30


def test_vision_provider_rejects_unsupported_mime_type() -> None:
    provider = OllamaVisionProvider("moondream", "http://localhost:11434")
    with pytest.raises(ProviderError, match="unsupported_image"):
        provider.analyze(b"image", "image/gif")
