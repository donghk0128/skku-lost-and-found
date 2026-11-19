"""Application service that turns AI output into post-ready draft data."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.ai.schemas import (
    AIChatRequest,
    AIChatResponse,
    AIDraftCreateRequest,
    AIDraftResponse,
    LocationOption,
)
from app.ai.workflow import run_chat_workflow
from app.core.errors import ApiError
from app.ai.core.providers import DraftProvider
from app.ai.core.schemas import DraftRequest, PostDraft
from app.ai.knowledge.location_retriever import LocationMatch, find_locations
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
                locale=request.locale,
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
        matches = location_matches if location_matches is not None else (
            find_locations(request.natural_language, locale=request.locale)
            if request.locale == "en"
            else find_locations(request.natural_language)
        )
        location_candidates = [match.resolved_name for match in matches]
        duplicate_names = {
            name for name in location_candidates if location_candidates.count(name) > 1
        }
        campus_labels = (
            {"HSSC": "Humanities and Social Sciences Campus", "NSC": "Natural Sciences Campus"}
            if request.locale == "en"
            else {"HSSC": "인문사회과학캠퍼스", "NSC": "자연과학캠퍼스"}
        )
        location_options = [
            LocationOption(
                id=match.location.location_id,
                campus=match.location.campus,
                name=match.resolved_name,
                label=(
                    f"{campus_labels[match.location.campus]} {match.resolved_name}"
                    if match.resolved_name in duplicate_names
                    and match.location.campus in campus_labels
                    else match.resolved_name
                ),
            )
            for match in matches
            if match.location.location_id is not None
        ]
        option_ids = {option.id for option in location_options}
        unknown_ids = set(request.selected_location_ids) - option_ids
        if unknown_ids:
            raise ApiError(
                422,
                "invalid_location_selection",
                "현재 장소 후보에 포함된 장소만 선택할 수 있습니다.",
            )
        selected_location_ids = request.selected_location_ids or (
            [location_options[0].id] if len(location_options) == 1 else []
        )
        selected_names = [
            option.name for option in location_options if option.id in selected_location_ids
        ]
        if location_confirmed:
            location_text = request.confirmed_location.text
        elif selected_names:
            location_text = ", ".join(selected_names)
        else:
            location_text = None
        missing_fields = [
            field
            for field in result.draft.missing_fields
            if not (field == "location" and location_confirmed)
            and not (field == "event_time" and event_time_confirmed)
        ]
        if not location_confirmed and not selected_names and "location" not in missing_fields:
            missing_fields.append("location")
        if (location_confirmed or selected_names) and "location" in missing_fields:
            missing_fields.remove("location")
        warnings = list(result.draft.warnings)
        if not location_confirmed and not matches and result.draft.location_text is not None:
            warnings.append(
                "The location is not in the campus directory and could not be confirmed automatically."
                if request.locale == "en"
                else "학교 장소 사전에 없는 위치는 자동으로 확정하지 않았습니다."
            )
        return AIDraftResponse(
            post_type=request.post_type,
            title=result.draft.title,
            description=result.draft.description,
            item_name=result.draft.item_name,
            category_id=category.id,
            category_code=category.code,
            location_text=location_text,
            location_candidates=location_candidates,
            location_options=location_options,
            selected_location_ids=selected_location_ids,
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
            locale=request.locale,
            user_messages=[message.content for message in request.messages],
            draft_generator=lambda conversation, location_matches: AIDraftService.generate(
                db,
                AIDraftCreateRequest(
                    post_type=request.post_type,
                    locale=request.locale,
                    natural_language=conversation,
                    selected_location_ids=request.selected_location_ids,
                    confirmed_location=request.confirmed_location,
                ),
                provider,
                location_matches,
            ),
            previous_draft=None if request.confirmed_location else request.draft,
            pending_field=None if request.confirmed_location else request.pending_field,
            collected_fields=request.collected_fields,
        )
        return AIChatResponse(
            status=state["status"],
            assistant_message=state["assistant_message"],
            draft=state["draft"],
            pending_field=state.get("pending_field"),
            collected_fields=state.get("collected_fields", {}),
            selected_location_ids=state["draft"].selected_location_ids,
        )
