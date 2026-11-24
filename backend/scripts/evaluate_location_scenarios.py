"""Replay v4/v5 rankings with counterfactual extra pins, without changing the DB.

Requires a saved result.json from the fixed benchmark and its unchanged dataset.
The scenarios are stress tests selected by hand, not independent accuracy evidence.
"""

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from math import exp
from pathlib import Path

from app.matching.evaluation import ranking_metrics
from app.matching.ranking import COLOR_CONFLICT_PENALTY, RULE_WEIGHT, SEMANTIC_WEIGHT
from app.matching.scoring import LOCATION_WEIGHT, _haversine_km


def evaluate(snapshot: dict, dataset: dict, scenario_data: dict) -> dict:
    posts = {
        f"{kind}:{pair['code']}": pair[kind]
        for pair in dataset["pairs"] for kind in ("lost", "found")
    }
    anchors = dataset["anchors"]
    if len(snapshot["pairs"]) != 2 * len(dataset["pairs"]) ** 2:
        raise ValueError("Snapshot must contain all pairs from the fixed benchmark")

    def pins(key: str, extras: dict[str, list[str]]) -> list[tuple[float, float]]:
        entry = posts[key]
        names = ([entry["anchor"]] if entry["anchor"] is not None else []) + extras.get(key, [])
        return [tuple(anchors[name]) for name in names]

    def score(row: dict, source_key: str, candidate_key: str, extras: dict[str, list[str]]) -> float:
        source_pins, candidate_pins = pins(source_key, extras), pins(candidate_key, extras)
        distance = min(
            (_haversine_km(left, right) for left in source_pins for right in candidate_pins),
            default=None,
        )
        old_location = row["signals"]["location"]
        new_location = exp(-distance / 3) if distance is not None else 0.0
        raw_rule = row["rule_score"] - LOCATION_WEIGHT * old_location + LOCATION_WEIGHT * new_location
        ranked_rule = raw_rule / (1 - LOCATION_WEIGHT) if distance is None else raw_rule
        return max(0.0, RULE_WEIGHT * ranked_rule + SEMANTIC_WEIGHT * row["semantic_score"]
                   - (COLOR_CONFLICT_PENALTY if row["signals"]["color_conflict"] else 0.0))

    results = []
    for scenario in scenario_data["scenarios"]:
        extras = scenario["extra_pins"]
        if any(key not in posts or any(name not in anchors for name in names) for key, names in extras.items()):
            raise ValueError(f"Unknown post or anchor in {scenario['code']}")
        grouped: dict[str, list[dict]] = defaultdict(list)
        positives: dict[str, set[str]] = {}
        score_changes = []
        for row in snapshot["pairs"]:
            source_kind = "lost" if row["source_type"] == "LOST" else "found"
            candidate_kind = "found" if source_kind == "lost" else "lost"
            source_key = f"{source_kind}:{row['source']}"
            candidate_key = f"{candidate_kind}:{row['candidate']}"
            v4_score = score(row, source_key, candidate_key, {})
            v5_score = score(row, source_key, candidate_key, extras)
            recorded_v4 = row.get("variant_scores", {}).get("missing_geo_reweighted")
            if recorded_v4 is not None and abs(recorded_v4 - v4_score) > 0.00001:
                raise ValueError(f"Snapshot v4 score differs for {source_key}/{candidate_key}")
            if abs(v5_score - v4_score) >= 0.001:
                score_changes.append({
                    "source": source_key, "candidate": candidate_key, "label": row["label"],
                    "v4_score": round(v4_score, 4), "v5_score": round(v5_score, 4),
                    "delta": round(v5_score - v4_score, 4),
                })
            grouped[source_key].append({
                "candidate": candidate_key,
                "label": row["label"],
                "tie_rank": row["ranks"]["hybrid_v3"],
                "v4_score": v4_score,
                "v5_score": v5_score,
            })
            if row["label"]:
                positives[source_key] = {candidate_key}
        v4_rankings = {
            source: [item["candidate"] for item in sorted(rows, key=lambda item: (-item["v4_score"], item["tie_rank"]))]
            for source, rows in grouped.items()
        }
        v5_rankings = {
            source: [item["candidate"] for item in sorted(rows, key=lambda item: (-item["v5_score"], item["tie_rank"]))]
            for source, rows in grouped.items()
        }
        changes = []
        for source in sorted(grouped):
            correct = next(iter(positives[source]))
            old_rank = v4_rankings[source].index(correct) + 1
            new_rank = v5_rankings[source].index(correct) + 1
            if old_rank != new_rank or v4_rankings[source][0] != v5_rankings[source][0]:
                changes.append({"source": source, "positive": correct, "v4_rank": old_rank,
                                "v5_rank": new_rank, "v4_top": v4_rankings[source][0],
                                "v5_top": v5_rankings[source][0]})
        results.append({
            "code": scenario["code"], "hypothesis": scenario["hypothesis"],
            "extra_pins": extras,
            "metrics": {"v4": ranking_metrics(v4_rankings, positives),
                        "v5": ranking_metrics(v5_rankings, positives)},
            "metrics_by_direction": {
                direction: {
                    "v4": ranking_metrics({key: value for key, value in v4_rankings.items() if key.startswith(prefix)}, positives),
                    "v5": ranking_metrics({key: value for key, value in v5_rankings.items() if key.startswith(prefix)}, positives),
                }
                for direction, prefix in (("LOST_TO_FOUND", "lost:"), ("FOUND_TO_LOST", "found:"))
            },
            "changed_queries": changes,
            "score_changed_pairs": len(score_changes),
            "largest_score_changes": sorted(score_changes, key=lambda item: abs(item["delta"]), reverse=True)[:5],
        })
    report = {"generated_at": datetime.now(timezone.utc).isoformat(),
            "source_algorithm_version": snapshot["algorithm_version"],
            "scenario_set": scenario_data["name"], "source_count": len(positives),
            "results": results}
    if scenario_data.get("sweep_single_extra_pin"):
        sweep = []
        for key in sorted(posts):
            for anchor in sorted(anchors):
                if anchor == posts[key]["anchor"]:
                    continue
                case = evaluate(snapshot, dataset, {"name": "single-pin-sweep", "scenarios": [{
                    "code": f"{key}+{anchor}", "hypothesis": "Systematic single extra pin",
                    "extra_pins": {key: [anchor]},
                }]})["results"][0]
                sweep.append(case)
        baseline = sweep[0]["metrics"]["v4"]
        improved = [case for case in sweep if case["metrics"]["v5"]["mrr"] > baseline["mrr"]]
        worsened = [case for case in sweep if case["metrics"]["v5"]["mrr"] < baseline["mrr"]]
        changed = [case for case in sweep if case["changed_queries"]]
        report["single_extra_pin_sweep"] = {
            "case_count": len(sweep), "baseline": baseline,
            "mrr_improved_cases": len(improved), "mrr_worsened_cases": len(worsened),
            "ranking_changed_cases": len(changed),
            "largest_effects": sorted(
                sweep, key=lambda case: (
                    abs(case["metrics"]["v5"]["mrr"] - baseline["mrr"]),
                    max((abs(item["delta"]) for item in case["largest_score_changes"]), default=0.0),
                ), reverse=True,
            )[:10],
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--dataset", type=Path, default=Path("evaluation/benchmark_v1.json"))
    parser.add_argument("--scenarios", type=Path, default=Path("evaluation/location_scenarios_v1.json"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(
        json.loads(args.snapshot.read_text(encoding="utf-8")),
        json.loads(args.dataset.read_text(encoding="utf-8")),
        json.loads(args.scenarios.read_text(encoding="utf-8")),
    )
    result["input_sha256"] = {
        "snapshot": hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
        "dataset": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "scenarios": hashlib.sha256(args.scenarios.read_bytes()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "output": str(args.output),
        "source_count": result["source_count"],
        "scenarios": [
            {
                "code": case["code"],
                "v4": case["metrics"]["v4"],
                "v5": case["metrics"]["v5"],
                "positive_rank_or_top_changed_queries": len(case["changed_queries"]),
                "score_changed_pairs": case["score_changed_pairs"],
            }
            for case in result["results"]
        ],
        "input_sha256": result["input_sha256"],
    }
    if "single_extra_pin_sweep" in result:
        sweep = result["single_extra_pin_sweep"]
        summary["single_extra_pin_sweep"] = {
            key: sweep[key]
            for key in ("case_count", "baseline", "mrr_improved_cases",
                        "mrr_worsened_cases", "ranking_changed_cases")
        }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
