"""Ollama and OpenAI adapters for structured image analysis."""

import base64
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import ValidationError

from .providers import ProviderError
from .vision_prompt import VISION_SYSTEM_PROMPT, VISION_USER_PROMPT
from .vision_schemas import ImageAttributes, VisionResult, VisionUsage, vision_json_schema


class VisionProvider(ABC):
    """Analyze one in-memory image without persisting it."""

    @abstractmethod
    def analyze(self, image: bytes, mime_type: str) -> VisionResult:
        """Return validated observable attributes for one image."""


class HttpVisionProvider(VisionProvider):
    """Provide bounded retry behavior for vision APIs."""

    def __init__(self, model: str, timeout_seconds: float):
        self.model = model
        self.timeout_seconds = timeout_seconds

    def analyze(self, image: bytes, mime_type: str) -> VisionResult:
        if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ProviderError("unsupported_image")
        for attempt in range(3):
            try:
                return self._analyze_once(image, mime_type)
            except ProviderError as error:
                if error.kind not in {"timeout", "rate_limited", "unavailable"} or attempt == 2:
                    raise
                time.sleep(0.25 * (2**attempt))
        raise ProviderError("unavailable")

    @abstractmethod
    def _analyze_once(self, image: bytes, mime_type: str) -> VisionResult:
        """Perform one provider request."""

    def _post(self, url: str, **kwargs: Any) -> tuple[dict[str, Any], float]:
        started = time.perf_counter()
        try:
            response = httpx.post(url, timeout=self.timeout_seconds, **kwargs)
        except httpx.TimeoutException as error:
            raise ProviderError("timeout") from error
        except httpx.HTTPError as error:
            raise ProviderError("unavailable") from error
        duration = time.perf_counter() - started
        if response.status_code == 429:
            raise ProviderError("rate_limited")
        if response.status_code >= 500:
            raise ProviderError("unavailable")
        if response.status_code >= 400:
            raise ProviderError("rejected", f"HTTP {response.status_code}")
        try:
            return response.json(), duration
        except ValueError as error:
            raise ProviderError("invalid_response") from error


class OllamaVisionProvider(HttpVisionProvider):
    """Analyze images with a local Ollama vision model."""

    def __init__(self, model: str, base_url: str, timeout_seconds: float = 120):
        super().__init__(model, timeout_seconds)
        self.base_url = base_url.rstrip("/")

    def _analyze_once(self, image: bytes, mime_type: str) -> VisionResult:
        payload, duration = self._post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": VISION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": VISION_USER_PROMPT,
                        "images": [base64.b64encode(image).decode("ascii")],
                    },
                ],
                "format": vision_json_schema(),
                "stream": False,
                "options": {"temperature": 0},
            },
        )
        try:
            attributes = ImageAttributes.model_validate_json(payload["message"]["content"])
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            raise ProviderError("invalid_response") from error
        return VisionResult(
            attributes=attributes,
            usage=VisionUsage(
                input_tokens=payload.get("prompt_eval_count"),
                output_tokens=payload.get("eval_count"),
                duration_seconds=duration,
            ),
            provider="ollama",
            model=self.model,
        )


class OpenAIVisionProvider(HttpVisionProvider):
    """Analyze images with the OpenAI Responses API."""

    def __init__(self, model: str, api_key: str, base_url: str, timeout_seconds: float = 120):
        super().__init__(model, timeout_seconds)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _analyze_once(self, image: bytes, mime_type: str) -> VisionResult:
        if not self.api_key:
            raise ProviderError("not_configured")
        data_url = f"data:{mime_type};base64,{base64.b64encode(image).decode('ascii')}"
        payload, duration = self._post(
            f"{self.base_url}/responses",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "store": False,
                "input": [
                    {"role": "system", "content": VISION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": VISION_USER_PROMPT},
                            {"type": "input_image", "image_url": data_url, "detail": "low"},
                        ],
                    },
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "lost_item_image_attributes",
                        "strict": True,
                        "schema": vision_json_schema(),
                    }
                },
            },
        )
        if payload.get("status") == "incomplete":
            raise ProviderError("incomplete")
        try:
            attributes = ImageAttributes.model_validate_json(self._output_text(payload))
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            raise ProviderError("invalid_response") from error
        usage = payload.get("usage") or {}
        return VisionResult(
            attributes=attributes,
            usage=VisionUsage(
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                duration_seconds=duration,
            ),
            provider="openai",
            model=self.model,
        )

    @staticmethod
    def _output_text(payload: dict[str, Any]) -> str:
        for output in payload.get("output", []):
            for content in output.get("content", []):
                if content.get("type") == "refusal":
                    raise ProviderError("refused")
                if content.get("type") == "output_text":
                    return content["text"]
        raise ProviderError("invalid_response")
