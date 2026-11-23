"""Public recommendation endpoint."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.service import get_current_user
from app.core.database import get_db
from app.matching.ranking import ALGORITHM_VERSION
from app.matching.schemas import RankedCandidateItem, RankedCandidateListResponse, RecommendationItem, RecommendationListResponse
from app.matching.service import MatchingService
from app.posts.schemas import PostResponse
from app.users.model import User


router = APIRouter(prefix="/posts", tags=["matching"])


@router.get("/{post_id}/ranked-candidates", response_model=RankedCandidateListResponse)
def list_ranked_candidates(
    post_id: UUID,
    category_id: int | None = Query(default=None, ge=1),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RankedCandidateListResponse:
    source, ranked, total, run_id = MatchingService.ranked_candidates(
        db, post_id, current_user.id, category_id, q, limit, offset
    )
    return RankedCandidateListResponse(
        source_post_id=source.id,
        run_id=run_id,
        algorithm_version=ALGORITHM_VERSION,
        items=[
            RankedCandidateItem(
                post=PostResponse.model_validate(item.post),
                rank=offset + index,
                score=round(item.score, 4),
                rule_score=round(item.signals.ranking_score, 4),
                semantic_score=round(item.semantic_score, 4) if item.semantic_score is not None else None,
                reasons=item.reasons,
            )
            for index, item in enumerate(ranked, start=1)
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


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
