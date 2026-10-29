"""Authenticated API endpoint for AI-assisted post drafts."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.schemas import AIChatRequest, AIChatResponse, AIDraftCreateRequest, AIDraftResponse
from app.ai.service import AIDraftService
from app.auth.service import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.integrations.ai.core.providers import DraftProvider, OllamaProvider, OpenAIProvider, ProviderError, provider_error_message
from app.users.model import User


router = APIRouter(prefix="/ai", tags=["ai"])


def get_draft_provider() -> DraftProvider:
    """Create the server-selected provider without exposing credentials to clients."""

    settings = get_settings()
    if settings.ai_provider == "ollama":
        return OllamaProvider(settings.ai_model, settings.ollama_base_url, settings.ai_timeout_seconds)
    return OpenAIProvider(
        settings.ai_model,
        settings.openai_api_key,
        settings.openai_base_url,
        settings.ai_timeout_seconds,
    )


@router.post("/post-drafts", response_model=AIDraftResponse)
def create_post_draft(
    request: AIDraftCreateRequest,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: DraftProvider = Depends(get_draft_provider),
) -> AIDraftResponse:
    """Return a validated editable draft; nothing is persisted during generation."""

    try:
        return AIDraftService.generate(db, request, provider)
    except ProviderError as error:
        status_code = 429 if error.kind == "rate_limited" else 503
        raise ApiError(status_code, f"ai_{error.kind}", provider_error_message(error)) from error


@router.post("/post-draft-chat", response_model=AIChatResponse)
def continue_post_draft_chat(
    request: AIChatRequest,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: DraftProvider = Depends(get_draft_provider),
) -> AIChatResponse:
    """Continue a stateless, text-only post drafting conversation."""

    try:
        return AIDraftService.continue_chat(db, request, provider)
    except ProviderError as error:
        status_code = 429 if error.kind == "rate_limited" else 503
        raise ApiError(status_code, f"ai_{error.kind}", provider_error_message(error)) from error
