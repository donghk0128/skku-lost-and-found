"""Request and response shapes for the first post endpoints."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


PostType = Literal["LOST", "FOUND"]
PostStatus = Literal["OPEN", "COMPLETED"]
CreationMethod = Literal["MANUAL", "AI_ASSISTED"]


class PostCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    post_type: PostType
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_id: UUID
    post_type: PostType
    title: str
    description: str
    status: PostStatus
    creation_method: CreationMethod
    created_at: datetime
    updated_at: datetime
