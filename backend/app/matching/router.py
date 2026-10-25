"""Public recommendation endpoint."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.matching.schemas import RecommendationItem, RecommendationListResponse
from app.matching.service import MatchingService
from app.posts.schemas import PostResponse


router = APIRouter(prefix="/posts", tags=["matching"])


@router.get("/{post_id}/recommendations", response_model=RecommendationListResponse)
def list_recommendations(
    post_id: UUID,
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> RecommendationListResponse:
    source, ranked = MatchingService.recommend(db, post_id, limit)
    return RecommendationListResponse(
        source_post_id=source.id,
        items=[
            RecommendationItem(post=PostResponse.model_validate(candidate), score=round(score, 4))
            for candidate, score in ranked
        ],
    )
