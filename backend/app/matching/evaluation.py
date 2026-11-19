"""Metrics for a fully labeled set of candidate pairs."""

from collections.abc import Mapping
from uuid import UUID


def ranking_metrics(rankings: Mapping[UUID, list[UUID]], positives: Mapping[UUID, set[UUID]]) -> dict[str, float]:
    """Macro-average recall@1, recall@5 and reciprocal rank across source posts."""
    if not rankings:
        raise ValueError("At least one source post is required")
    totals = {"recall_at_1": 0.0, "recall_at_5": 0.0, "mrr": 0.0}
    for source_id, ordered_ids in rankings.items():
        truth = positives[source_id]
        if not truth:
            raise ValueError(f"No positive candidate for source {source_id}")
        totals["recall_at_1"] += len(truth.intersection(ordered_ids[:1])) / len(truth)
        totals["recall_at_5"] += len(truth.intersection(ordered_ids[:5])) / len(truth)
        totals["mrr"] += next((1 / rank for rank, candidate_id in enumerate(ordered_ids, 1) if candidate_id in truth), 0.0)
    return {name: round(value / len(rankings), 4) for name, value in totals.items()}
