"""Business rules for computing post recommendations on request."""

from uuid import UUID
from uuid import uuid4
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.matching.model import PostEmbedding, RecommendationItem, RecommendationRun
from app.matching.ranking import ALGORITHM_VERSION, RankedCandidate, rank_candidates
from app.matching.repository import MatchingRepository
from app.matching.scoring import score_posts
from app.posts.model import Post
from app.posts.service import PostService


MAX_SEMANTIC_CANDIDATES = 50


class MatchingService:
    @staticmethod
    def ranked_candidates(
        db: Session,
        post_id: UUID,
        user_id: UUID,
        category_id: int | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[Post, list[RankedCandidate], int, UUID]:
        source = PostService.get_visible_by_id(db, post_id)
        if source.author_id != user_id:
            raise ApiError(403, "post_forbidden", "본인 게시글만 비교 기준으로 선택할 수 있습니다.")
        if source.status != "OPEN":
            raise ApiError(422, "source_post_completed", "진행 중인 게시글을 선택해 주세요.")
        if search is not None:
            search = search.strip()
            if not search:
                raise ApiError(422, "invalid_search_query", "검색어를 입력해 주세요.")
        candidates = MatchingRepository.list_candidates(db, source, category_id, search)
        similarities = MatchingRepository.cosine_similarities(db, source, [post.id for post in candidates])
        ranked = rank_candidates(source, candidates, similarities)
        filters = {"post_type": "FOUND" if source.post_type == "LOST" else "LOST", "category_id": category_id, "q": search}
        run_id = MatchingService._record_run(db, source, candidates, ranked, filters)
        return source, ranked[offset : offset + limit], len(ranked), run_id

    @staticmethod
    def _record_run(
        db: Session, source: Post, candidates: list[Post], ranked: list[RankedCandidate], filters: dict
    ) -> UUID:
        # The fingerprint identifies the inputs, not a cached result. Scores are still recomputed on every request.
        signature = {
            "algorithm": ALGORITHM_VERSION,
            "source": [str(source.id), source.updated_at.isoformat()],
            "filters": filters,
            "candidates": sorted((str(post.id), post.updated_at.isoformat()) for post in candidates),
            "embeddings": sorted(
                (str(post_id), model, content_hash, updated_at.isoformat())
                for post_id, model, content_hash, updated_at in db.execute(
                    select(PostEmbedding.post_id, PostEmbedding.model, PostEmbedding.content_hash, PostEmbedding.updated_at)
                    .where(PostEmbedding.post_id.in_([source.id, *(post.id for post in candidates)]))
                ).all()
            ),
        }
        fingerprint = hashlib.sha256(json.dumps(signature, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        existing_id = db.scalar(select(RecommendationRun.id).where(RecommendationRun.fingerprint == fingerprint))
        if existing_id is not None:
            return existing_id
        run_id = uuid4()
        try:
            with db.begin_nested():
                db.add(RecommendationRun(
                    id=run_id,
                    source_post_id=source.id,
                    algorithm_version=ALGORITHM_VERSION,
                    fingerprint=fingerprint,
                    filters=filters,
                    candidate_count=len(candidates),
                ))
                db.flush()
                db.add_all(
                    RecommendationItem(
                        run_id=run_id,
                        candidate_post_id=item.post.id,
                        rank=index,
                        final_score=item.score,
                        rule_score=item.signals.score,
                        semantic_score=item.semantic_score,
                        text_score=item.signals.text,
                        category_score=item.signals.category,
                        time_score=item.signals.time,
                        location_score=item.signals.location,
                        distance_km=item.signals.distance_km,
                        time_gap_hours=item.signals.time_gap_hours,
                        reasons=item.reasons,
                    )
                    for index, item in enumerate(ranked, start=1)
                )
                db.flush()
            db.commit()
        except IntegrityError:
            db.rollback()
            existing_id = db.scalar(select(RecommendationRun.id).where(RecommendationRun.fingerprint == fingerprint))
            if existing_id is None:
                raise
            return existing_id
        return run_id

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
