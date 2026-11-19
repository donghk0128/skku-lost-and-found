"""Explainable ranking of already-filtered candidates."""

from dataclasses import dataclass
from uuid import UUID

from app.matching.scoring import RuleSignals, rule_signals
from app.posts.model import Post

ALGORITHM_VERSION = "hybrid-v2"


@dataclass(frozen=True)
class RankedCandidate:
    post: Post
    signals: RuleSignals
    semantic_score: float | None
    score: float
    reasons: list[str]


def rank_candidates(
    source: Post, candidates: list[Post], similarities: dict[UUID, float]
) -> list[RankedCandidate]:
    ranked = []
    for candidate in candidates:
        signals = rule_signals(source, candidate)
        semantic = similarities.get(candidate.id)
        score = signals.score if semantic is None else 0.7 * signals.score + 0.3 * semantic
        reasons = []
        if signals.distance_km is not None and signals.distance_km <= 0.5:
            reasons.append("NEARBY_LOCATION")
        if signals.time_gap_hours is not None and signals.time_gap_hours == 0:
            reasons.append("OVERLAPPING_TIME")
        if signals.category == 1:
            reasons.append("SAME_CATEGORY")
        if semantic is not None and semantic >= 0.75:
            reasons.append("SIMILAR_MEANING")
        ranked.append(RankedCandidate(candidate, signals, semantic, score, reasons))
    ranked.sort(key=lambda item: (item.score, item.post.created_at, str(item.post.id)), reverse=True)
    return ranked
