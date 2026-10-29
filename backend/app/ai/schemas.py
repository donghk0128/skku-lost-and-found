"""HTTP contracts for AI-assisted post draft generation."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from app.integrations.ai.core.schemas import TimePrecision

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError


PostType = Literal["LOST", "FOUND"]
RequiredDraftField = Literal["item_name", "location", "event_time"]


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
    natural_language: str = Field(min_length=1, max_length=4000)
    confirmed_location: ConfirmedLocation | None = None
    confirmed_event_start_at: AwareDatetime | None = None
    confirmed_event_end_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_event_time(self) -> Self:
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


class AIDraftResponse(BaseModel):
    """Validated, editable fields returned to the client without provider internals."""

    post_type: PostType
    title: str
    description: str
    item_name: str | None
    category_id: int
    category_code: str
    location_text: str | None
    location_candidates: list[str] = Field(default_factory=list)
    latitude: float | None
    longitude: float | None
    event_start_at: datetime | None
    event_end_at: datetime | None
    time_precision: TimePrecision | None = None
    keywords: list[str]
    missing_fields: list[str]
    warnings: list[str]


class AIChatMessage(BaseModel):
    """One user answer retained by the client for a stateless chat request."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["user"] = "user"
    content: str = Field(min_length=1, max_length=2000)


class AIChatRequest(BaseModel):
    """Complete user-side conversation sent on each drafting turn."""

    model_config = ConfigDict(extra="forbid")

    post_type: PostType
    messages: list[AIChatMessage] = Field(min_length=1, max_length=12)
    draft: AIDraftResponse | None = None
    pending_field: RequiredDraftField | None = None
    collected_fields: dict[RequiredDraftField, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_total_content_length(self) -> Self:
        if sum(len(message.content) for message in self.messages) > 3600:
            raise PydanticCustomError(
                "chat_content_too_long",
                "전체 대화 내용은 3,600자 이하여야 합니다.",
            )
        return self


class AIChatResponse(BaseModel):
    """Next assistant prompt and the latest editable draft."""

    status: Literal["NEEDS_INPUT", "READY"]
    assistant_message: str
    draft: AIDraftResponse
    pending_field: RequiredDraftField | None = None
    collected_fields: dict[RequiredDraftField, str] = Field(default_factory=dict)
