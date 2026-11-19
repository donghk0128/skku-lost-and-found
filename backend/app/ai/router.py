"""Authenticated API endpoint for AI-assisted post drafts."""

import mimetypes

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.ai.schemas import AIChatRequest, AIChatResponse, AIDraftCreateRequest, AIDraftResponse
from app.ai.service import AIDraftService
from app.auth.service import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.ai.core.providers import DraftProvider, OllamaProvider, OpenAIProvider, ProviderError, provider_error_message
from app.ai.core.vision_providers import OllamaVisionProvider, OpenAIVisionProvider, VisionProvider
from app.ai.core.vision_schemas import MAX_IMAGE_BYTES, MAX_IMAGE_COUNT, ImageInput
from app.ai.core.vision_service import validate_images
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
        settings.ai_reasoning_effort,
    )


def get_vision_provider() -> VisionProvider:
    """Create the independently configurable image-analysis provider."""

    settings = get_settings()
    if settings.ai_provider == "ollama":
        return OllamaVisionProvider(settings.ai_vision_model, settings.ollama_base_url, settings.ai_timeout_seconds)
    return OpenAIVisionProvider(
        settings.ai_vision_model,
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


@router.post("/post-draft-chat-with-images", response_model=AIChatResponse)
async def continue_post_draft_chat_with_images(
    payload: str = Form(...),
    images: list[UploadFile] = File(...),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: DraftProvider = Depends(get_draft_provider),
    vision_provider: VisionProvider = Depends(get_vision_provider),
) -> AIChatResponse:
    """Analyze newly attached images without persisting their bytes."""

    try:
        request = AIChatRequest.model_validate_json(payload)
    except ValidationError as error:
        raise ApiError(422, "validation_error", "요청 형식이 올바르지 않습니다.") from error
    try:
        if len(images) > MAX_IMAGE_COUNT:
            raise ProviderError("too_many_images")
        image_inputs = []
        for image in images:
            mime_type = image.content_type or mimetypes.guess_type(image.filename or "")[0]
            if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
                raise ProviderError("unsupported_image")
            image_inputs.append(
                ImageInput(
                    content=await image.read(MAX_IMAGE_BYTES + 1),
                    mime_type=mime_type,
                )
            )
        validate_images(image_inputs)
        response = AIDraftService.continue_chat(
            db,
            request,
            provider,
            image_inputs,
            vision_provider,
        )
        if not response.images_analyzed:
            raise ProviderError("unavailable")
        return response
    except ProviderError as error:
        status_code = 429 if error.kind == "rate_limited" else 422 if error.kind in {
            "empty_image",
            "too_many_images",
            "image_too_large",
            "invalid_image",
            "unsupported_image",
        } else 503
        raise ApiError(status_code, f"ai_{error.kind}", provider_error_message(error)) from error
