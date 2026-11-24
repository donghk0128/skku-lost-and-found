"""The fixed benchmark must remain balanced and fully labeled in both directions."""

import csv
from collections import defaultdict
from pathlib import Path

from scripts.seed_matching_benchmark import load_dataset, location_values, locations_for, write_labels


DATASET = Path(__file__).parents[1] / "evaluation" / "benchmark_v1.json"
MULTI_LOCATION_DATASET = Path(__file__).parents[1] / "evaluation" / "benchmark_multi_location_v1.json"
HOLDOUT_DATASET = Path(__file__).parents[1] / "evaluation" / "benchmark_multi_location_holdout_v1.json"


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


def test_multi_location_benchmark_has_balanced_labels_and_secondary_coordinates(tmp_path: Path) -> None:
    data = load_dataset(MULTI_LOCATION_DATASET)
    assert len(data["pairs"]) == 8
    assert len({pair["code"] for pair in data["pairs"]}) == 8
    assert all(
        len(locations_for(data, pair[kind])) >= 1
        for pair in data["pairs"] for kind in ("lost", "found")
    )
    assert sum(
        len(locations_for(data, pair[kind])) > 1
        for pair in data["pairs"] for kind in ("lost", "found")
    ) == 8
    text_only_first = locations_for(data, data["pairs"][2]["lost"])
    assert location_values(data, text_only_first[0])[1:] == (None, None)
    assert location_values(data, text_only_first[1])[1] is not None

    output = tmp_path / "multi_location_labels.csv"
    write_labels(data, output)
    by_source = defaultdict(list)
    with output.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            by_source[row["source_post_id"]].append(row)
    assert len(by_source) == 16
    assert all(len(rows) == 8 and sum(int(row["label"]) for row in rows) == 1 for rows in by_source.values())
    assert sum(len(rows) for rows in by_source.values()) == 128


def test_multi_location_holdout_is_balanced_and_covers_missing_and_multiple_pins(tmp_path: Path) -> None:
    data = load_dataset(HOLDOUT_DATASET)
    assert len(data["pairs"]) == 16
    assert len({pair["code"] for pair in data["pairs"]}) == 16
    assert {category: sum(pair["category_code"] == category for pair in data["pairs"])
            for category in ("WALLET", "ELECTRONICS", "KEY", "OTHER")} == {
                "WALLET": 4, "ELECTRONICS": 4, "KEY": 4, "OTHER": 4,
            }
    entries = [pair[kind] for pair in data["pairs"] for kind in ("lost", "found")]
    assert sum(len(entry["locations"]) >= 3 for entry in entries) >= 4
    assert sum(entry["locations"][0]["anchor"] is None for entry in entries) >= 4
    assert any(all(location["anchor"] is None for location in entry["locations"]) for entry in entries)

    output = tmp_path / "holdout_labels.csv"
    write_labels(data, output)
    by_source = defaultdict(list)
    with output.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            by_source[row["source_post_id"]].append(row)
    assert len(by_source) == 32
    assert all(len(rows) == 16 and sum(int(row["label"]) for row in rows) == 1 for rows in by_source.values())
    assert sum(len(rows) for rows in by_source.values()) == 512
