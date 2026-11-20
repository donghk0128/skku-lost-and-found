"""Application service that turns AI output into post-ready draft data."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.ai.location_options import build_location_options
from app.ai.schemas import (
    AIChatRequest,
    AIChatResponse,
    AIDraftCreateRequest,
    AIDraftResponse,
    AIRequiredFields,
)
from app.ai.workflow import run_chat_workflow
from app.core.errors import ApiError
from app.ai.core.providers import DraftProvider
from app.ai.core.schemas import DraftRequest, PostDraft, RequiredFields
from app.ai.core.vision_providers import VisionProvider
from app.ai.core.vision_schemas import ImageInput, MergedImageAttributes
from app.ai.core.vision_service import VisionAnalysisService
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
        image_attributes: MergedImageAttributes | None = None,
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
        draft = result.draft
        if image_attributes:
            image_fields = VisionAnalysisService.draft_fields(image_attributes, request.locale)
            same_item = bool(
                draft.item_name
                and image_fields.item_name
                and draft.item_name.casefold().strip()
                == image_fields.item_name.casefold().strip()
            )
            compatible = (
                not draft.item_name
                or not image_fields.item_name
                or same_item
                or draft.category_code == image_fields.category_code
            )
            updates: dict[str, object] = {
                "warnings": list(dict.fromkeys([*draft.warnings, *image_fields.warnings]))[:10],
            }
            if compatible:
                updates.update({
                    "keywords": list(
                        dict.fromkeys([*draft.keywords, *image_fields.keywords])
                    )[:10],
                    "description": " ".join(
                        value
                        for value in (draft.description, image_fields.description)
                        if value
                    )[:4000],
                })
            if compatible and not draft.item_name and image_fields.item_name:
                updates.update({
                    "item_name": image_fields.item_name,
                    "category_code": (
                        image_fields.category_code
                        if image_fields.category_code != "OTHER"
                        else draft.category_code
                    ),
                    "title": image_fields.title or draft.title,
                    "missing_fields": [
                        field for field in draft.missing_fields if field != "item_name"
                    ],
                })
            draft = draft.model_copy(update=updates)

        category = PostRepository.get_category_by_code(db, draft.category_code)
        if category is None:
            raise ApiError(503, "ai_category_unavailable", "AI 카테고리 설정을 확인해 주세요.")

        location_confirmed = request.confirmed_location is not None
        event_time_confirmed = request.confirmed_event_start_at is not None
        confirmed_precision = (
            "EXACT"
            if request.confirmed_event_start_at == request.confirmed_event_end_at
            else "RANGE"
        )
        event_start_at, event_end_at = AIDraftService._event_range(draft)
        matches = location_matches if location_matches is not None else (
            find_locations(request.natural_language, locale=request.locale)
            if request.locale == "en"
            else find_locations(request.natural_language)
        )
        location_candidates = [match.resolved_name for match in matches]
        location_options = build_location_options(matches, request.locale)
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
            for field in draft.missing_fields
            if not (field == "location" and location_confirmed)
            and not (field == "event_time" and event_time_confirmed)
        ]
        if not location_confirmed and not selected_names and "location" not in missing_fields:
            missing_fields.append("location")
        if (location_confirmed or selected_names) and "location" in missing_fields:
            missing_fields.remove("location")
        warnings = list(draft.warnings)
        if not location_confirmed and not matches and draft.location_text is not None:
            warnings.append(
                "The location is not in the campus directory and could not be confirmed automatically."
                if request.locale == "en"
                else "학교 장소 사전에 없는 위치는 자동으로 확정하지 않았습니다."
            )
        return AIDraftResponse(
            post_type=request.post_type,
            title=draft.title,
            description=draft.description,
            item_name=draft.item_name,
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
            time_precision=(confirmed_precision if event_time_confirmed else draft.time_precision),
            keywords=draft.keywords,
            missing_fields=missing_fields,
            warnings=warnings,
        )

    @staticmethod
    def _event_range(draft: PostDraft | RequiredFields) -> tuple[datetime | None, datetime | None]:
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
    def continue_chat(
        db: Session,
        request: AIChatRequest,
        provider: DraftProvider,
        images: list[ImageInput] | None = None,
        vision_provider: VisionProvider | None = None,
    ) -> AIChatResponse:
        """Run one stateless chat turn with optional in-memory images."""

        if request.pending_field == "location_selection":
            if request.required_fields is None:
                raise ApiError(422, "missing_location_draft", "장소 후보 초안이 필요합니다.")
            option_ids = {option.id for option in request.required_fields.location_options}
            if request.selected_location_ids and set(request.selected_location_ids) - option_ids:
                raise ApiError(
                    422,
                    "invalid_location_selection",
                    "현재 장소 후보에 포함된 장소만 선택할 수 있습니다.",
                )

        def extract_fields(
            conversation: str, location_matches: tuple[LocationMatch, ...]
        ) -> AIRequiredFields:
            extracted = provider.extract_required_fields(
                DraftRequest(
                    post_type=request.post_type,
                    locale=request.locale,
                    natural_language=conversation,
                    reference_time=datetime.now(ZoneInfo("Asia/Seoul")),
                )
            )
            start_at, end_at = AIDraftService._event_range(extracted)
            options = build_location_options(location_matches, request.locale)
            selected_ids = [options[0].id] if len(options) == 1 else []
            names = [option.name for option in options if option.id in selected_ids]
            missing = [field for field in extracted.missing_fields if field != "location"]
            if not extracted.item_name:
                missing.append("item_name")
            if extracted.event_start_date is None or extracted.event_end_date is None:
                missing.append("event_time")
            if not names:
                missing.append("location")
            return AIRequiredFields(
                item_name=extracted.item_name,
                location_text=", ".join(names) or None,
                location_candidates=[option.name for option in options],
                location_options=options,
                selected_location_ids=selected_ids,
                event_start_at=start_at,
                event_end_at=end_at,
                time_precision=extracted.time_precision,
                missing_fields=list(dict.fromkeys(missing)),
            )

        state = run_chat_workflow(
            post_type=request.post_type,
            locale=request.locale,
            user_messages=[message.content for message in request.messages],
            field_extractor=extract_fields,
            draft_generator=lambda conversation, location_matches, image_attributes: AIDraftService.generate(
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
                image_attributes,
            ),
            previous_required_fields=(
                None if request.confirmed_location else request.required_fields
            ),
            pending_field=None if request.confirmed_location else request.pending_field,
            selected_location_ids=request.selected_location_ids,
            location_correction=request.location_correction,
            images=images,
            image_analyzer=(
                VisionAnalysisService(vision_provider).analyze
                if images and vision_provider
                else None
            ),
            image_attributes=request.image_attributes,
        )
        return AIChatResponse(
            status=state["status"],
            assistant_message=state["assistant_message"],
            draft=state.get("draft"),
            required_fields=state["fields"],
            pending_field=state.get("pending_field"),
            collected_fields=request.collected_fields,
            selected_location_ids=state["fields"].selected_location_ids,
            images_analyzed=state.get("images_analyzed", False),
            image_attributes=state.get("image_attributes"),
        )
