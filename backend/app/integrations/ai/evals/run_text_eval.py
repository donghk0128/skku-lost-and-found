"""Run one provider/model against the shared labeled JSONL dataset."""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError

from core.providers import ProviderError
from core.schemas import GoldCase
from core.service import create_provider, generate_draft
from evals.metrics import score_draft, summarize


ROOT = Path(__file__).resolve().parent


def load_cases(path: Path) -> list[GoldCase]:
    """Load and validate JSONL gold cases."""

    return [GoldCase.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_prices(model: str) -> tuple[float, float, int]:
    """Load a dated price snapshot for one model, or zero for local models."""

    pricing = json.loads((ROOT / "pricing.json").read_text(encoding="utf-8"))
    model_price = pricing["models"].get(model, {"input": 0, "output": 0})
    return model_price["input"], model_price["output"], pricing["unit_tokens"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["ollama", "openai"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset", type=Path, default=ROOT / "dataset.jsonl")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()

    cases = load_cases(args.dataset)
    provider = create_provider(args.provider, args.model)
    input_price, output_price, price_unit = load_prices(args.model)
    rows: list[dict] = []

    # Warm-up is intentionally excluded from measurements.
    try:
        provider.generate(cases[0].request)
    except ProviderError:
        pass

    for case in cases:
        row = {"id": case.id, "provider": args.provider, "model": args.model}
        try:
            result = generate_draft(provider, case.request)
            input_tokens = result.usage.input_tokens or 0
            output_tokens = result.usage.output_tokens or 0
            cost = (input_tokens * input_price + output_tokens * output_price) / price_unit
            row.update(
                status="ok",
                duration_seconds=result.usage.duration_seconds,
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                cost_usd=cost,
                scores=score_draft(case.expected, result.draft),
                actual=result.draft.model_dump(mode="json"),
            )
        except (ProviderError, ValidationError) as error:
            row.update(status="error", error_kind=getattr(error, "kind", "validation"))
        rows.append(row)

    summary = summarize(rows)
    if summary["successful"]:
        summary["estimated_cost_per_1000_drafts_usd"] = summary["measured_cost_usd"] / summary["successful"] * 1000
    else:
        summary["estimated_cost_per_1000_drafts_usd"] = 0
    summary.update(provider=args.provider, model=args.model, evaluated_at=datetime.now().astimezone().isoformat())

    args.output_dir.mkdir(parents=True, exist_ok=True)
    slug = f"{args.provider}-{args.model.replace(':', '-') }"
    (args.output_dir / f"{slug}.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (args.output_dir / f"{slug}.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=summary.keys())
        writer.writeheader()
        writer.writerow(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
