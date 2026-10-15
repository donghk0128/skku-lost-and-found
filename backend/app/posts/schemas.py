"""Request and response shapes for post endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError


PostType = Literal["LOST", "FOUND"]
PostStatus = Literal["OPEN", "COMPLETED"]
CreationMethod = Literal["MANUAL", "AI_ASSISTED"]


def validate_location_and_time(
    latitude: Decimal | None,
    longitude: Decimal | None,
    event_start_at: datetime | None,
    event_end_at: datetime | None,
) -> None:
    if (latitude is None) != (longitude is None):
        raise PydanticCustomError("coordinates_pair", "위도와 경도를 함께 입력해 주세요.")
    if (event_start_at is None) != (event_end_at is None):
        raise PydanticCustomError("event_time_pair", "발생 시작·끝 시각을 함께 입력해 주세요.")
    if event_start_at is not None and event_end_at is not None and event_start_at > event_end_at:
        raise PydanticCustomError("event_time_order", "발생 시작 시각이 끝 시각보다 늦을 수 없습니다.")


class PostCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    post_type: PostType
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)
    item_name: str | None = Field(default=None, min_length=1, max_length=100)
    category_id: int | None = Field(default=None, ge=1)
    location_text: str | None = Field(default=None, min_length=1, max_length=255)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)
    event_start_at: AwareDatetime | None = None
    event_end_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_details(self) -> Self:
        validate_location_and_time(
            self.latitude,
            self.longitude,
            self.event_start_at,
            self.event_end_at,
        )
        return self


class PostUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=1)
    item_name: str | None = Field(default=None, min_length=1, max_length=100)
    category_id: int | None = Field(default=None, ge=1)
    location_text: str | None = Field(default=None, min_length=1, max_length=255)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)
    event_start_at: AwareDatetime | None = None
    event_end_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise PydanticCustomError("post_update_empty", "수정할 필드를 하나 이상 입력해 주세요.")
        if any(getattr(self, field) is None for field in {"title", "description"} & self.model_fields_set):
            raise PydanticCustomError("post_update_null", "제목과 설명에 null을 사용할 수 없습니다.")
        for first, second in (("latitude", "longitude"), ("event_start_at", "event_end_at")):
            if (first in self.model_fields_set) != (second in self.model_fields_set):
                raise PydanticCustomError("post_update_pair", f"{first}와 {second}를 함께 수정해 주세요.")
        validate_location_and_time(
            self.latitude,
            self.longitude,
            self.event_start_at,
            self.event_end_at,
        )
        return self


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_id: UUID
    post_type: PostType
    title: str
    description: str
    item_name: str | None
    category_id: int | None
    location_text: str | None
    latitude: float | None
    longitude: float | None
    event_start_at: datetime | None
    event_end_at: datetime | None
    status: PostStatus
    creation_method: CreationMethod
    created_at: datetime
    updated_at: datetime


class PostListResponse(BaseModel):
    items: list[PostResponse]
    total: int
    limit: int
    offset: int


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class PostImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    content_type: str
    position: int
    created_at: datetime
    content_url: str
