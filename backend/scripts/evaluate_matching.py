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


def evaluate(path: Path) -> dict:
    labels = load_labels(path)
    methods: dict[str, dict[UUID, list[UUID]]] = {"rule": {}, "semantic": {}, "hybrid": {}}
    positives: dict[UUID, set[UUID]] = {}
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
            for candidate_index, item in enumerate(ranked, start=1):
                pair_snapshots.append({
                    "source": f"S{source_index}",
                    "candidate": f"S{source_index}-C{candidate_index}",
                    "label": int(candidate_labels[item.post.id]),
                    "rule_score": round(item.signals.score, 6),
                    "semantic_score": round(item.semantic_score, 6),
                    "hybrid_score": round(item.score, 6),
                    "signals": {
                        "text": round(item.signals.text, 6),
                        "category": round(item.signals.category, 6),
                        "time": round(item.signals.time, 6),
                        "location": round(item.signals.location, 6),
                        "color_conflict": item.signals.color_conflict,
                    },
                })
            methods["hybrid"][source_id] = [item.post.id for item in ranked]
            methods["rule"][source_id] = [item.post.id for item in sorted(ranked, key=lambda item: (item.signals.score, item.post.created_at, str(item.post.id)), reverse=True)]
            methods["semantic"][source_id] = [item.post.id for item in sorted(ranked, key=lambda item: (item.semantic_score, item.post.created_at, str(item.post.id)), reverse=True)]
            positives[source_id] = {candidate_id for candidate_id, is_match in candidate_labels.items() if is_match}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "algorithm_version": ALGORITHM_VERSION,
        "label_file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "scoring": {
            "rule_weight": RULE_WEIGHT,
            "semantic_weight": SEMANTIC_WEIGHT,
            "color_conflict_penalty": COLOR_CONFLICT_PENALTY,
        },
        "embedding_model": MODEL,
        "source_count": len(labels),
        "labeled_pair_count": sum(map(len, labels.values())),
        "metrics": {method: ranking_metrics(rankings, positives) for method, rankings in methods.items()},
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
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
