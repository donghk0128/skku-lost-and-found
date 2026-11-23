"""Compare ranking variants against a manually labeled, isolated candidate set.

Run from backend: python -m scripts.evaluate_matching --labels evaluation/labels.csv --output evaluation/result.json
This script never calls Gemini and never writes to the database.
"""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.database import engine
from app.matching.embedding import MODEL
from app.matching.evaluation import ranking_metrics
from app.matching.ranking import ALGORITHM_VERSION, COLOR_CONFLICT_PENALTY, RULE_WEIGHT, SEMANTIC_WEIGHT, rank_candidates
from app.matching.repository import MatchingRepository
from app.posts.model import Post


def load_labels(path: Path) -> dict[UUID, dict[UUID, bool]]:
    labels: dict[UUID, dict[UUID, bool]] = defaultdict(dict)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"source_post_id", "candidate_post_id", "label"}.issubset(reader.fieldnames or []):
            raise ValueError("CSV requires source_post_id,candidate_post_id,label")
        for row in reader:
            source_id, candidate_id = UUID(row["source_post_id"]), UUID(row["candidate_post_id"])
            if row["label"] not in {"0", "1"}:
                raise ValueError("Labels must be 0 or 1")
            if candidate_id in labels[source_id]:
                raise ValueError(f"Duplicate pair: {source_id}, {candidate_id}")
            labels[source_id][candidate_id] = row["label"] == "1"
    if not labels:
        raise ValueError("CSV contains no pairs")
    return labels


def load_codes(path: Path) -> dict[UUID, str]:
    """Use optional benchmark codes in reports without exposing post UUIDs."""
    codes = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("source_code"):
                codes[UUID(row["source_post_id"])] = row["source_code"]
            if row.get("candidate_code"):
                codes[UUID(row["candidate_post_id"])] = row["candidate_code"]
    return codes


def evaluate(path: Path) -> dict:
    labels = load_labels(path)
    codes = load_codes(path)
    methods: dict[str, dict[UUID, list[UUID]]] = {
        name: {} for name in ("rule", "semantic", "hybrid_v3", "no_color", "no_color_low_text")
    }
    positives: dict[UUID, set[UUID]] = {}
    source_types: dict[UUID, str] = {}
    pair_snapshots = []
    with Session(engine) as db:
        if db.get_bind().dialect.name != "postgresql":
            raise ValueError("Evaluation needs the migrated PostgreSQL/pgvector database")
        for source_index, (source_id, candidate_labels) in enumerate(labels.items(), start=1):
            source = db.get(Post, source_id)
            if source is None or source.status != "OPEN" or source.deleted_at is not None:
                raise ValueError(f"Source is missing or closed: {source_id}")
            candidates = [db.get(Post, candidate_id) for candidate_id in candidate_labels]
            if any(post is None or post.status != "OPEN" or post.deleted_at is not None or post.post_type == source.post_type for post in candidates):
                raise ValueError(f"Invalid candidate for source {source_id}")
            candidates = [post for post in candidates if post is not None]
            similarities = MatchingRepository.cosine_similarities(db, source, list(candidate_labels))
            if len(similarities) != len(candidate_labels):
                raise ValueError(f"Missing compatible embeddings for source {source_id}")
            ranked = rank_candidates(source, candidates, similarities)
            items = {item.post.id: item for item in ranked}
            if any(item.semantic_score is None for item in ranked):
                raise ValueError(f"Missing semantic score for source {source_id}")
            scores = {
                candidate_id: {
                    "rule": item.signals.score,
                    "semantic": item.semantic_score,
                    "hybrid_v3": item.score,
                    "no_color": RULE_WEIGHT * item.signals.score + SEMANTIC_WEIGHT * item.semantic_score,
                    # Transfer 0.05 of total weight from lexical text to semantic similarity.
                    # Rule text falls from 0.15 to 0.05; final semantic rises from 0.50 to 0.55.
                    "no_color_low_text": (
                        RULE_WEIGHT * (item.signals.score - 0.10 * item.signals.text)
                        + (SEMANTIC_WEIGHT + 0.05) * item.semantic_score
                    ),
                }
                for candidate_id, item in items.items()
            }
            for method in methods:
                methods[method][source_id] = sorted(
                    items,
                    key=lambda candidate_id: (
                        scores[candidate_id][method],
                        items[candidate_id].post.created_at,
                        str(candidate_id),
                    ),
                    reverse=True,
                )
            ranks = {
                method: {
                    candidate_id: rank
                    for rank, candidate_id in enumerate(methods[method][source_id], start=1)
                }
                for method in methods
            }
            for candidate_index, candidate_id in enumerate(candidate_labels, start=1):
                item = items[candidate_id]
                pair_snapshots.append({
                    "source": codes.get(source_id, f"S{source_index}"),
                    "source_type": source.post_type,
                    "candidate": codes.get(candidate_id, f"S{source_index}-C{candidate_index}"),
                    "label": int(candidate_labels[candidate_id]),
                    "ranks": {method: ranks[method][candidate_id] for method in methods},
                    "rule_score": round(item.signals.score, 6),
                    "semantic_score": round(item.semantic_score, 6),
                    "hybrid_score": round(item.score, 6),
                    "variant_scores": {
                        method: round(scores[candidate_id][method], 6)
                        for method in ("no_color", "no_color_low_text")
                    },
                    "signals": {
                        "text": round(item.signals.text, 6),
                        "category": round(item.signals.category, 6),
                        "time": round(item.signals.time, 6),
                        "location": round(item.signals.location, 6),
                        "color_conflict": item.signals.color_conflict,
                    },
                })
            positives[source_id] = {candidate_id for candidate_id, is_match in candidate_labels.items() if is_match}
            source_types[source_id] = source.post_type
    directions = {
        "LOST_TO_FOUND": {source_id for source_id, post_type in source_types.items() if post_type == "LOST"},
        "FOUND_TO_LOST": {source_id for source_id, post_type in source_types.items() if post_type == "FOUND"},
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "algorithm_version": ALGORITHM_VERSION,
        "label_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "scoring": {
            "rule_weight": RULE_WEIGHT,
            "semantic_weight": SEMANTIC_WEIGHT,
            "color_conflict_penalty": COLOR_CONFLICT_PENALTY,
            "no_color_low_text": "rule text 0.05, category 0.25, time 0.30, location 0.30, rule multiplier 0.50, semantic 0.55, no color penalty",
        },
        "embedding_model": MODEL,
        "source_count": len(labels),
        "labeled_pair_count": sum(map(len, labels.values())),
        "sources_with_fewer_than_6_candidates": sum(len(pairs) < 6 for pairs in labels.values()),
        "metrics": {method: ranking_metrics(rankings, positives) for method, rankings in methods.items()},
        "metrics_by_direction": {
            direction: {
                method: ranking_metrics(
                    {source_id: ranking for source_id, ranking in rankings.items() if source_id in source_ids},
                    positives,
                )
                for method, rankings in methods.items()
            }
            for direction, source_ids in directions.items() if source_ids
        },
        "pairs": pair_snapshots,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(args.labels)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "pairs"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
