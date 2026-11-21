from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RoomCreate(Request):
    post_id: UUID


class RoomClose(Request):
    reason: Literal["RETURNED", "GENERAL"]


class TextMessageCreate(Request):
    content: str = Field(min_length=1, max_length=2000)
    client_message_id: str | None = Field(default=None, min_length=1, max_length=64)


class ReadUpdate(Request):
    sequence: int = Field(ge=0)


class VisibilityUpdate(Request):
    is_hidden: bool


class MessageImageResponse(BaseModel):
    id: UUID
    position: int
    content_type: str
    image_url: str


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    room_id: UUID
    sender_id: UUID | None
    sequence: int
    message_type: Literal["TEXT", "IMAGE"]
    content: str | None
    images: list[MessageImageResponse] = Field(default_factory=list)
    client_message_id: str | None = None
    image_content_type: str | None = None
    image_url: str | None = None
    created_at: datetime


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    post_id: UUID | None
    owner_id: UUID | None
    requester_id: UUID | None
    post_title: str
    other_nickname: str
    post_deleted: bool = False
    other_withdrawn: bool = False
    status: Literal["ACTIVE", "CLOSED"]
    close_reason: Literal["RETURNED", "GENERAL", "POST_COMPLETED"] | None
    closed_at: datetime | None
    created_at: datetime
    last_read_sequence: int
    last_read_at: datetime | None
    is_hidden: bool
    unread_count: int
    last_message: MessageResponse | None


class RoomListResponse(BaseModel):
    items: list[RoomResponse]
    total: int
    limit: int
    offset: int


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    next_after: int
    has_more: bool
