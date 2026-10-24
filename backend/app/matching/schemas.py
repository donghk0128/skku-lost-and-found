"""API response models for recommendations."""

from uuid import UUID

from pydantic import BaseModel, Field

from app.posts.schemas import PostResponse


class RecommendationItem(BaseModel):
    post: PostResponse
    score: float = Field(ge=0, le=1)


class RecommendationListResponse(BaseModel):
    source_post_id: UUID
    items: list[RecommendationItem]
