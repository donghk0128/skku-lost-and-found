"""The fixed benchmark must remain balanced and fully labeled in both directions."""

import csv
from collections import defaultdict
from pathlib import Path

from scripts.seed_matching_benchmark import load_dataset, write_labels


DATASET = Path(__file__).parents[1] / "evaluation" / "benchmark_v1.json"


def test_benchmark_has_one_positive_among_twelve_candidates_in_each_direction(tmp_path: Path) -> None:
    data = load_dataset(DATASET)
    assert len(data["pairs"]) == 12
    assert {pair["category_code"] for pair in data["pairs"]} == {
        "ELECTRONICS", "WALLET", "KEY", "OTHER"
    }
    output = tmp_path / "labels.csv"
    write_labels(data, output)
    by_source = defaultdict(list)
    with output.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            by_source[row["source_post_id"]].append(row)
    assert len(by_source) == 24
    assert all(len(rows) == 12 and sum(int(row["label"]) for row in rows) == 1 for rows in by_source.values())
    assert sum(len(rows) for rows in by_source.values()) == 288
    assert sum(pair[kind]["anchor"] is None for pair in data["pairs"] for kind in ("lost", "found")) == 3
