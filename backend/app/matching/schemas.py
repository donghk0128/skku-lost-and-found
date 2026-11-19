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


class RankedCandidateItem(BaseModel):
    post: PostResponse
    rank: int
    score: float = Field(ge=0, le=1)
    rule_score: float = Field(ge=0, le=1)
    semantic_score: float | None = Field(default=None, ge=0, le=1)
    reasons: list[str]


class RankedCandidateListResponse(BaseModel):
    source_post_id: UUID
    run_id: UUID
    algorithm_version: str
    items: list[RankedCandidateItem]
    total: int
    limit: int
    offset: int
