"""Direct Ollama and OpenAI adapters for the standalone prototype."""

import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import ValidationError

from .prompt import build_messages
from .schemas import DraftRequest, GenerationResult, PostDraft, Usage, strict_json_schema


class ProviderError(Exception):
    """Expose a safe failure kind without retaining private prompt content."""

    def __init__(self, kind: str, detail: str = ""):
        self.kind = kind
        self.detail = detail
        super().__init__(kind)


class DraftProvider(ABC):
    """Generate one validated post draft."""

    @abstractmethod
    def generate(self, request: DraftRequest) -> GenerationResult:
        """Generate a draft from one normalized request."""


class HttpProvider(DraftProvider):
    """Provide bounded retry behavior shared by HTTP providers."""

    def __init__(self, model: str, timeout_seconds: float):
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, request: DraftRequest) -> GenerationResult:
        for attempt in range(3):
            try:
                return self._generate_once(request)
            except ProviderError as error:
                retryable = error.kind in {"timeout", "rate_limited", "unavailable"}
                if not retryable or attempt == 2:
                    raise
                time.sleep(0.25 * (2**attempt))
        raise ProviderError("unavailable")

    @abstractmethod
    def _generate_once(self, request: DraftRequest) -> GenerationResult:
        """Perform one request without retrying."""

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


class OllamaProvider(HttpProvider):
    """Use a locally running Ollama chat API."""

    def __init__(self, model: str, base_url: str, timeout_seconds: float = 120):
        super().__init__(model, timeout_seconds)
        self.base_url = base_url.rstrip("/")

    def _generate_once(self, request: DraftRequest) -> GenerationResult:
        payload, duration = self._post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": build_messages(request),
                "format": strict_json_schema(),
                "stream": False,
                "options": {"temperature": 0},
            },
        )
        try:
            draft = PostDraft.model_validate_json(payload["message"]["content"])
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            raise ProviderError("invalid_response") from error
        return GenerationResult(
            draft=draft,
            usage=Usage(
                input_tokens=payload.get("prompt_eval_count"),
                output_tokens=payload.get("eval_count"),
                duration_seconds=duration,
            ),
            provider="ollama",
            model=self.model,
        )


class OpenAIProvider(HttpProvider):
    """Use OpenAI Responses API with strict Structured Outputs."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 120,
        reasoning_effort: str = "none",
    ):
        super().__init__(model, timeout_seconds)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.reasoning_effort = reasoning_effort

    def _generate_once(self, request: DraftRequest) -> GenerationResult:
        if not self.api_key:
            raise ProviderError("not_configured")
        payload, duration = self._post(
            f"{self.base_url}/responses",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "reasoning": {"effort": self.reasoning_effort},
                "input": build_messages(request),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "lost_and_found_post_draft",
                        "strict": True,
                        "schema": strict_json_schema(),
                    }
                },
            },
        )
        if payload.get("status") == "incomplete":
            raise ProviderError("incomplete")
        try:
            draft = PostDraft.model_validate_json(self._output_text(payload))
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            raise ProviderError("invalid_response") from error
        usage = payload.get("usage") or {}
        return GenerationResult(
            draft=draft,
            usage=Usage(
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


class FakeProvider(DraftProvider):
    """Return a deterministic draft for tests and offline UI development."""

    def __init__(self, draft: PostDraft):
        self.draft = draft

    def generate(self, request: DraftRequest) -> GenerationResult:
        return GenerationResult(
            draft=self.draft,
            usage=Usage(input_tokens=0, output_tokens=0, duration_seconds=0),
            provider="fake",
            model="fake",
        )


def provider_error_message(error: ProviderError) -> str:
    """Translate safe provider errors into actionable Korean UI messages."""

    messages = {
        "timeout": "모델 응답 시간이 초과되었습니다.",
        "rate_limited": "요청 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.",
        "unavailable": "모델 서버에 연결할 수 없습니다.",
        "rejected": "모델 서버가 요청을 거절했습니다.",
        "refused": "모델이 해당 입력 처리를 거부했습니다.",
        "incomplete": "모델 응답이 완료되지 않았습니다.",
        "invalid_response": "모델 응답이 게시글 스키마와 일치하지 않습니다.",
        "not_configured": "OpenAI API key가 설정되지 않았습니다.",
        "unsupported_image": "지원하지 않는 이미지 형식입니다.",
    }
    return messages.get(error.kind, "알 수 없는 모델 오류가 발생했습니다.")
