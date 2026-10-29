"""Application service that turns AI output into post-ready draft data."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.ai.schemas import AIChatRequest, AIChatResponse, AIDraftCreateRequest, AIDraftResponse
from app.ai.workflow import run_chat_workflow
from app.core.errors import ApiError
from app.integrations.ai.core.providers import DraftProvider
from app.integrations.ai.core.schemas import DraftRequest, PostDraft
from app.integrations.ai.knowledge.location_retriever import LocationMatch, find_locations
from app.posts.repository import PostRepository


class AIDraftService:
    """Keep provider output separate from application and database contracts."""

    @staticmethod
    def generate(
        db: Session,
        request: AIDraftCreateRequest,
        provider: DraftProvider,
        location_matches: tuple[LocationMatch, ...] | None = None,
    ) -> AIDraftResponse:
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
        confirmed_precision = (
            "EXACT"
            if request.confirmed_event_start_at == request.confirmed_event_end_at
            else "RANGE"
        )
        event_start_at, event_end_at = AIDraftService._event_range(result.draft)
        matches = location_matches if location_matches is not None else find_locations(request.natural_language)
        location_candidates = [match.resolved_name for match in matches]
        if location_confirmed:
            location_text = request.confirmed_location.text
        elif len(matches) == 1:
            location_text = matches[0].resolved_name
        else:
            location_text = None
        missing_fields = [
            field
            for field in result.draft.missing_fields
            if not (field == "location" and location_confirmed)
            and not (field == "event_time" and event_time_confirmed)
        ]
        if not location_confirmed and len(matches) != 1 and "location" not in missing_fields:
            missing_fields.append("location")
        if (location_confirmed or len(matches) == 1) and "location" in missing_fields:
            missing_fields.remove("location")
        warnings = list(result.draft.warnings)
        if len(matches) > 1:
            warnings.append("여러 학교 장소가 발견되어 사용자 확인이 필요합니다.")
        elif not matches and result.draft.location_text is not None:
            warnings.append("학교 장소 사전에 없는 위치는 자동으로 확정하지 않았습니다.")
        return AIDraftResponse(
            post_type=request.post_type,
            title=result.draft.title,
            description=result.draft.description,
            item_name=result.draft.item_name,
            category_id=category.id,
            category_code=category.code,
            location_text=location_text,
            location_candidates=location_candidates,
            latitude=(float(request.confirmed_location.latitude) if location_confirmed else None),
            longitude=(float(request.confirmed_location.longitude) if location_confirmed else None),
            event_start_at=(request.confirmed_event_start_at if event_time_confirmed else event_start_at),
            event_end_at=(request.confirmed_event_end_at if event_time_confirmed else event_end_at),
            time_precision=(confirmed_precision if event_time_confirmed else result.draft.time_precision),
            keywords=result.draft.keywords,
            missing_fields=missing_fields,
            warnings=warnings,
        )

    @staticmethod
    def _event_range(draft: PostDraft) -> tuple[datetime | None, datetime | None]:
        """Convert extracted date and optional time precision into a KST range."""

        start_date = draft.event_start_date
        end_date = draft.event_end_date
        if start_date is None or end_date is None:
            return None, None
        zone = ZoneInfo("Asia/Seoul")
        precision = draft.time_precision
        if precision == "DATE_ONLY":
            return datetime.combine(start_date, time.min, zone), datetime.combine(end_date, time.max, zone)
        if draft.event_start_time is None or draft.event_end_time is None:
            raise ValueError("event times are required for time-specific precision")
        start_at = datetime.combine(start_date, draft.event_start_time, zone)
        end_at = datetime.combine(end_date, draft.event_end_time, zone)
        if precision == "APPROXIMATE":
            return start_at - timedelta(minutes=30), end_at + timedelta(minutes=30)
        return start_at, end_at

    @staticmethod
    def continue_chat(db: Session, request: AIChatRequest, provider: DraftProvider) -> AIChatResponse:
        """Run the text-only LangGraph workflow for one stateless chat turn."""

        state = run_chat_workflow(
            post_type=request.post_type,
            user_messages=[message.content for message in request.messages],
            draft_generator=lambda conversation, location_matches: AIDraftService.generate(
                db,
                AIDraftCreateRequest(
                    post_type=request.post_type,
                    natural_language=conversation,
                ),
                provider,
                location_matches,
            ),
            previous_draft=request.draft,
            pending_field=request.pending_field,
            collected_fields=request.collected_fields,
        )
        return AIChatResponse(
            status=state["status"],
            assistant_message=state["assistant_message"],
            draft=state["draft"],
            pending_field=state.get("pending_field"),
            collected_fields=state.get("collected_fields", {}),
        )
