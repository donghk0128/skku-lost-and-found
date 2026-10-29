"""Deterministic metrics for structured post-draft evaluation."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from statistics import median
from typing import Iterable

from core.schemas import PostDraft


def token_f1(expected: str | None, actual: str | None) -> float:
    """Calculate bag-of-token F1 after lightweight Korean-safe normalization."""

    expected_tokens = re.findall(r"[0-9A-Za-z가-힣]+", (expected or "").lower())
    actual_tokens = re.findall(r"[0-9A-Za-z가-힣]+", (actual or "").lower())
    if not expected_tokens and not actual_tokens:
        return 1.0
    if not expected_tokens or not actual_tokens:
        return 0.0
    overlap = sum((Counter(expected_tokens) & Counter(actual_tokens)).values())
    precision = overlap / len(actual_tokens)
    recall = overlap / len(expected_tokens)
    return 2 * precision * recall / (precision + recall) if overlap else 0.0


def set_f1(expected: Iterable[str], actual: Iterable[str]) -> float:
    """Calculate set F1 for missing-field labels."""

    expected_set, actual_set = set(expected), set(actual)
    if not expected_set and not actual_set:
        return 1.0
    if not expected_set or not actual_set:
        return 0.0
    overlap = len(expected_set & actual_set)
    return 2 * overlap / (len(expected_set) + len(actual_set))


def date_match(expected: date | None, actual: date | None) -> float:
    """Score extracted calendar dates."""

    if expected is None and actual is None:
        return 1.0
    if expected is None or actual is None:
        return 0.0
    return float(expected == actual)


def score_draft(expected: PostDraft, actual: PostDraft) -> dict[str, float]:
    """Score one validated draft against its gold label."""

    start_score = date_match(expected.event_start_date, actual.event_start_date)
    end_score = date_match(expected.event_end_date, actual.event_end_date)
    return {
        "category_accuracy": float(expected.category_code == actual.category_code),
        "item_name_f1": token_f1(expected.item_name, actual.item_name),
        "location_f1": token_f1(expected.location_text, actual.location_text),
        "time_accuracy": (start_score + end_score) / 2,
        "missing_fields_f1": set_f1(expected.missing_fields, actual.missing_fields),
    }


def percentile(values: list[float], percent: float) -> float:
    """Return a nearest-rank percentile without third-party dependencies."""

    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percent)))
    return ordered[index]


def summarize(rows: list[dict]) -> dict:
    """Aggregate successful scores, errors, latency, tokens, and cost."""

    successes = [row for row in rows if row["status"] == "ok"]
    scores = [row["scores"] for row in successes]
    latencies = [row["duration_seconds"] for row in successes]
    metric_names = ["category_accuracy", "item_name_f1", "location_f1", "time_accuracy", "missing_fields_f1"]
    return {
        "cases": len(rows),
        "successful": len(successes),
        "schema_valid_rate": len(successes) / len(rows) if rows else 0,
        "error_rate": (len(rows) - len(successes)) / len(rows) if rows else 0,
        **{
            name: sum(score[name] for score in scores) / len(scores) if scores else 0
            for name in metric_names
        },
        "latency_p50_seconds": median(latencies) if latencies else 0,
        "latency_p95_seconds": percentile(latencies, 0.95),
        "input_tokens": sum(row.get("input_tokens") or 0 for row in successes),
        "output_tokens": sum(row.get("output_tokens") or 0 for row in successes),
        "measured_cost_usd": sum(row.get("cost_usd") or 0 for row in successes),
    }
