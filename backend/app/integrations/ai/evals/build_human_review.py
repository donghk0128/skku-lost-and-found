"""Create a blinded 20-case human-review sheet from an evaluation result."""

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("results") / "human_review.csv")
    args = parser.parse_args()

    payload = json.loads(args.result.read_text(encoding="utf-8"))
    successful = [row for row in payload["rows"] if row["status"] == "ok"]
    if len(successful) < 20:
        raise SystemExit("At least 20 successful rows are required")
    step = len(successful) / 20
    selected = [successful[min(int(index * step), len(successful) - 1)] for index in range(20)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["review_id", "case_id", "draft_json", "information_fidelity_1_5", "non_hallucination_1_5", "edit_readiness_1_5", "notes"]
    with args.output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for index, row in enumerate(selected, start=1):
            writer.writerow(
                {
                    "review_id": f"review-{index:02d}",
                    "case_id": row["id"],
                    "draft_json": json.dumps(row["actual"], ensure_ascii=False),
                    "information_fidelity_1_5": "",
                    "non_hallucination_1_5": "",
                    "edit_readiness_1_5": "",
                    "notes": "",
                }
            )
    print(f"Wrote 20 blinded rows to {args.output}")


if __name__ == "__main__":
    main()
