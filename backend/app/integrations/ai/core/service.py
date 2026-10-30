"""Provider selection and safe draft normalization."""

import os

from dotenv import load_dotenv

from .providers import DraftProvider, OllamaProvider, OpenAIProvider
from .schemas import DraftRequest, GenerationResult
from .vision_providers import OllamaVisionProvider, OpenAIVisionProvider, VisionProvider


load_dotenv()


def create_provider(provider: str, model: str) -> DraftProvider:
    """Create a provider from UI or CLI selections and local environment."""

    timeout = float(os.getenv("AI_TIMEOUT_SECONDS", "120"))
    if provider == "ollama":
        return OllamaProvider(model, os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"), timeout)
    if provider == "openai":
        return OpenAIProvider(
            model,
            os.getenv("OPENAI_API_KEY", ""),
            os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            timeout,
            os.getenv("AI_REASONING_EFFORT", "none"),
        )
    raise ValueError(f"Unsupported provider: {provider}")


def generate_draft(provider: DraftProvider, request: DraftRequest) -> GenerationResult:
    """Generate a validated draft without persisting user input."""

    return provider.generate(request)


def create_vision_provider(provider: str, model: str) -> VisionProvider:
    """Create a vision provider from UI selections and local environment."""
    timeout = float(os.getenv("AI_TIMEOUT_SECONDS", "120"))
    if provider == "ollama":
        return OllamaVisionProvider(model, os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"), timeout)
    if provider == "openai":
        return OpenAIVisionProvider(
            model,
            os.getenv("OPENAI_API_KEY", ""),
            os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            timeout,
        )
    raise ValueError(f"Unsupported provider: {provider}")
