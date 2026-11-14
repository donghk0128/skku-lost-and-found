"""Business rules for computing post recommendations on request."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.matching.repository import MatchingRepository
from app.matching.scoring import score_posts
from app.posts.model import Post
from app.posts.service import PostService


MAX_SEMANTIC_CANDIDATES = 50


class MatchingService:
    @staticmethod
    def recommend(db: Session, post_id: UUID, limit: int) -> tuple[Post, list[tuple[Post, float]]]:
        source = PostService.get_visible_by_id(db, post_id)
        if source.status != "OPEN":
            return source, []

        candidates = [
            (candidate, score_posts(source, candidate))
            for candidate in MatchingRepository.list_candidates(db, source)
        ]
        candidates.sort(key=lambda item: (item[1], item[0].created_at, str(item[0].id)), reverse=True)
        shortlist = candidates[:MAX_SEMANTIC_CANDIDATES]
        similarities = MatchingRepository.cosine_similarities(db, source, [post.id for post, _ in shortlist])
        ranked = []
        for candidate, rule_score in shortlist:
            semantic_score = similarities.get(candidate.id)
            score = rule_score if semantic_score is None else 0.7 * rule_score + 0.3 * semantic_score
            ranked.append((candidate, score))
        ranked.sort(key=lambda item: (item[1], item[0].created_at, str(item[0].id)), reverse=True)
        return source, ranked[:limit]
