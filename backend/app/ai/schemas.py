"""HTTP contracts for AI-assisted post draft generation."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from app.ai.core.schemas import TimePrecision
from app.ai.core.vision_schemas import MergedImageAttributes
from app.posts.schemas import PostCreateFields

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError


PostType = Literal["LOST", "FOUND"]
Locale = Literal["ko", "en"]
RequiredDraftField = Literal["item_name", "location", "event_time"]
PendingDraftField = Literal["item_name", "location", "location_selection", "event_time"]


class LocationOption(BaseModel):
    """One normalized campus-directory location offered for selection."""

    id: str
    campus: str | None = None
    name: str
    label: str


class ConfirmedLocation(BaseModel):
    """Location selected by the user, optionally including map coordinates."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=255)
    latitude: Decimal = Field(ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal = Field(ge=-180, le=180, max_digits=9, decimal_places=6)


class AIDraftCreateRequest(BaseModel):
    """Untrusted user input used to generate an editable post draft."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    post_type: PostType
    locale: Locale = "ko"
    natural_language: str = Field(min_length=1, max_length=4000)
    selected_location_ids: list[str] = Field(default_factory=list, max_length=20)
    confirmed_location: ConfirmedLocation | None = None
    confirmed_event_start_at: AwareDatetime | None = None
    confirmed_event_end_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_event_time(self) -> Self:
        if len(self.selected_location_ids) != len(set(self.selected_location_ids)):
            raise PydanticCustomError(
                "duplicate_location_selection",
                "같은 장소를 중복 선택할 수 없습니다.",
            )
        if (self.confirmed_event_start_at is None) != (self.confirmed_event_end_at is None):
            raise PydanticCustomError(
                "event_time_pair",
                "확정 발생 시작·끝 시각을 함께 입력해 주세요.",
            )
        if (
            self.confirmed_event_start_at is not None
            and self.confirmed_event_end_at is not None
            and self.confirmed_event_start_at > self.confirmed_event_end_at
        ):
            raise PydanticCustomError(
                "event_time_order",
                "확정 발생 시작 시각이 끝 시각보다 늦을 수 없습니다.",
            )
        return self


class AIDraftResponse(PostCreateFields):
    """Manual post-create fields plus AI review metadata."""

    category_id: int = Field(ge=1)
    category_code: str
    location_candidates: list[str] = Field(default_factory=list)
    location_options: list[LocationOption] = Field(default_factory=list)
    selected_location_ids: list[str] = Field(default_factory=list)
    time_precision: TimePrecision | None = None
    keywords: list[str]
    missing_fields: list[str]
    warnings: list[str]


class AIRequiredFields(BaseModel):
    """Required information collected before final draft generation."""

    item_name: str | None = None
    location_text: str | None = None
    location_candidates: list[str] = Field(default_factory=list)
    location_options: list[LocationOption] = Field(default_factory=list)
    selected_location_ids: list[str] = Field(default_factory=list)
    event_start_at: datetime | None = None
    event_end_at: datetime | None = None
    time_precision: TimePrecision | None = None
    missing_fields: list[RequiredDraftField] = Field(default_factory=list)


class AIChatMessage(BaseModel):
    """One user answer retained by the client for a stateless chat request."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["user"] = "user"
    content: str = Field(min_length=1, max_length=2000)


class AIChatRequest(BaseModel):
    """Conversation and optional confirmed map location sent on each drafting turn."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    post_type: PostType
    locale: Locale = "ko"
    messages: list[AIChatMessage] = Field(min_length=1, max_length=12)
    draft: AIDraftResponse | None = None
    required_fields: AIRequiredFields | None = None
    pending_field: PendingDraftField | None = None
    collected_fields: dict[RequiredDraftField, str] = Field(default_factory=dict)
    selected_location_ids: list[str] = Field(default_factory=list, max_length=20)
    location_correction: str | None = Field(default=None, min_length=1, max_length=255)
    confirmed_location: ConfirmedLocation | None = None
    image_attributes: MergedImageAttributes | None = None

    @model_validator(mode="after")
    def validate_total_content_length(self) -> Self:
        if sum(len(message.content) for message in self.messages) > 3600:
            raise PydanticCustomError(
                "chat_content_too_long",
                "전체 대화 내용은 3,600자 이하여야 합니다.",
            )
        if len(self.selected_location_ids) != len(set(self.selected_location_ids)):
            raise PydanticCustomError(
                "duplicate_location_selection",
                "같은 장소를 중복 선택할 수 없습니다.",
            )
        if self.selected_location_ids and self.location_correction:
            raise PydanticCustomError(
                "conflicting_location_answer",
                "장소 선택과 장소 정정은 동시에 입력할 수 없습니다.",
            )
        return self


class AIChatResponse(BaseModel):
    """Next assistant prompt and the latest editable draft."""

    status: Literal["NEEDS_INPUT", "READY"]
    assistant_message: str
    draft: AIDraftResponse | None = None
    required_fields: AIRequiredFields
    pending_field: PendingDraftField | None = None
    collected_fields: dict[RequiredDraftField, str] = Field(default_factory=dict)
    selected_location_ids: list[str] = Field(default_factory=list)
    images_analyzed: bool = False
    image_attributes: MergedImageAttributes | None = None
