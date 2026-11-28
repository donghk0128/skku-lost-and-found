"""Compare sequential and two-worker vision analysis on the same images."""

import argparse
import json
import time
from pathlib import Path

from app.ai.core.vision_providers import OpenAIVisionProvider
from app.ai.core.vision_schemas import ImageInput
from app.ai.core.vision_service import VisionAnalysisService
from app.core.config import get_settings


def run(service, images, names, locale, max_workers):
    started = time.perf_counter()
    result = service.analyze(images, locale, max_workers=max_workers)
    wall_seconds = time.perf_counter() - started
    return {
        "max_workers": max_workers,
        "wall_seconds": wall_seconds,
        "provider_duration_sum_seconds": result.usage.duration_seconds,
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
        "merged": result.model_dump(mode="json", exclude={"image_results", "usage"}),
        "images": [
            {
                "file": name,
                "provider_duration_seconds": image_result.usage.duration_seconds,
                "input_tokens": image_result.usage.input_tokens,
                "output_tokens": image_result.usage.output_tokens,
                "attributes": image_result.attributes.model_dump(mode="json"),
            }
            for name, image_result in zip(names, result.image_results)
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("image_dir", type=Path)
    parser.add_argument("--locale", choices=("ko", "en"), default="ko")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    names = [
        "cup-with-guitar.jpg",
        "cup-with-guitar-2.jpg",
        "cup-with-guitar-3.jpg",
        "cup-with-guitar-4.jpg",
    ]
    paths = [args.image_dir / name for name in names]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing benchmark images: {missing}")

    settings = get_settings()
    provider = OpenAIVisionProvider(
        settings.ai_vision_model,
        settings.openai_api_key,
        settings.openai_base_url,
        settings.ai_timeout_seconds,
    )
    service = VisionAnalysisService(provider)
    images = [ImageInput(content=path.read_bytes(), mime_type="image/jpeg") for path in paths]

    sequential = run(service, images, names, args.locale, 1)
    parallel = run(service, images, names, args.locale, 2)
    report = {
        "model": settings.ai_vision_model,
        "locale": args.locale,
        "runs_per_mode": 1,
        "sequential": sequential,
        "parallel": parallel,
        "comparison": {
            "wall_seconds_saved": sequential["wall_seconds"] - parallel["wall_seconds"],
            "speedup": sequential["wall_seconds"] / parallel["wall_seconds"],
            "input_token_delta": parallel["input_tokens"] - sequential["input_tokens"],
            "output_token_delta": parallel["output_tokens"] - sequential["output_tokens"],
            "merged_results_equal": sequential["merged"] == parallel["merged"],
        },
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
