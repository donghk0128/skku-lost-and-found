"""Application service that turns AI output into post-ready draft data."""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.ai.schemas import AIChatRequest, AIChatResponse, AIDraftCreateRequest, AIDraftResponse
from app.ai.workflow import run_chat_workflow
from app.core.errors import ApiError
from app.integrations.ai.core.providers import DraftProvider
from app.integrations.ai.core.schemas import DraftRequest
from app.posts.repository import PostRepository


class AIDraftService:
    """Keep provider output separate from application and database contracts."""

    @staticmethod
    def generate(db: Session, request: AIDraftCreateRequest, provider: DraftProvider) -> AIDraftResponse:
        """Generate, validate, and normalize an editable post draft."""

        result = provider.generate(
            DraftRequest(
                post_type=request.post_type,
                natural_language=request.natural_language,
                reference_time=datetime.now(ZoneInfo("Asia/Seoul")),
            )
        )
        category = PostRepository.get_category_by_code(db, result.draft.category_code)
        if category is None:
            raise ApiError(503, "ai_category_unavailable", "AI 카테고리 설정을 확인해 주세요.")

        location_confirmed = request.confirmed_location is not None
        event_time_confirmed = request.confirmed_event_start_at is not None
        missing_fields = [
            field
            for field in result.draft.missing_fields
            if not (field == "location" and location_confirmed)
            and not (field == "event_time" and event_time_confirmed)
        ]
        return AIDraftResponse(
            post_type=request.post_type,
            title=result.draft.title,
            description=result.draft.description,
            item_name=result.draft.item_name,
            category_id=category.id,
            category_code=category.code,
            location_text=(request.confirmed_location.text if location_confirmed else result.draft.location_text),
            latitude=(float(request.confirmed_location.latitude) if location_confirmed else None),
            longitude=(float(request.confirmed_location.longitude) if location_confirmed else None),
            event_start_at=(request.confirmed_event_start_at if event_time_confirmed else result.draft.event_start_at),
            event_end_at=(request.confirmed_event_end_at if event_time_confirmed else result.draft.event_end_at),
            keywords=result.draft.keywords,
            missing_fields=missing_fields,
            warnings=result.draft.warnings,
        )

    @staticmethod
    def continue_chat(db: Session, request: AIChatRequest, provider: DraftProvider) -> AIChatResponse:
        """Run the text-only LangGraph workflow for one stateless chat turn."""

        state = run_chat_workflow(
            post_type=request.post_type,
            user_messages=[message.content for message in request.messages],
            draft_generator=lambda conversation: AIDraftService.generate(
                db,
                AIDraftCreateRequest(
                    post_type=request.post_type,
                    natural_language=conversation,
                ),
                provider,
            ),
        )
        return AIChatResponse(
            status=state["status"],
            assistant_message=state["assistant_message"],
            draft=state["draft"],
        )
