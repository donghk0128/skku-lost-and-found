"""Validate and merge in-memory image analysis results."""

import json
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

from .providers import ProviderError
from .schemas import Locale
from .vision_providers import VisionProvider
from .vision_schemas import (
    MAX_IMAGE_BYTES,
    MAX_IMAGE_COUNT,
    ImageDraftFields,
    ImageInput,
    MergedImageAttributes,
    VisionResult,
    VisionUsage,
)

SIGNATURES = {
    "image/jpeg": lambda content: content.startswith(b"\xff\xd8\xff"),
    "image/png": lambda content: content.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda content: len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP",
}

WARNING_MESSAGES = {
    "ko": {
        "conflicting_item_name": "사진마다 물품 종류가 다르게 인식되었습니다.",
        "conflicting_brand": "사진마다 브랜드가 다르게 인식되었습니다.",
        "conflicting_category": "사진마다 카테고리가 다르게 인식되었습니다.",
        "conflicting_colors": "사진마다 색상이 다르게 인식되었습니다.",
    },
    "en": {
        "conflicting_item_name": "The item was identified differently across photos.",
        "conflicting_brand": "The brand was identified differently across photos.",
        "conflicting_category": "The category was identified differently across photos.",
        "conflicting_colors": "The colors were identified differently across photos.",
    },
}


def validate_images(images: list[ImageInput]) -> None:
    """Reject invalid input before any provider call."""

    if not images:
        raise ProviderError("empty_image")
    if len(images) > MAX_IMAGE_COUNT:
        raise ProviderError("too_many_images")
    for image in images:
        if not image.content:
            raise ProviderError("empty_image")
        if len(image.content) > MAX_IMAGE_BYTES:
            raise ProviderError("image_too_large")
        if not SIGNATURES[image.mime_type](image.content):
            raise ProviderError("invalid_image")


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _consensus(values: Iterable[str | None], field: str, warnings: list[str]) -> str | None:
    candidates = _unique(value for value in values if value)
    if len({value.casefold() for value in candidates}) > 1:
        warnings.append(f"conflicting_{field}")
        return None
    return candidates[0] if candidates else None


class VisionAnalysisService:
    """Analyze at most five images and merge their observations."""

    def __init__(self, provider: VisionProvider):
        self.provider = provider

    def analyze(
        self,
        images: list[ImageInput],
        locale: Locale = "ko",
        *,
        max_workers: int = 2,
    ) -> MergedImageAttributes:
        validate_images(images)
        worker_count = min(max(1, max_workers), len(images))
        if worker_count == 1:
            results = [self.provider.analyze(image.content, image.mime_type, locale) for image in images]
        else:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                results = list(executor.map(
                    lambda image: self.provider.analyze(image.content, image.mime_type, locale),
                    images,
                ))
        attributes = [result.attributes for result in results]
        warnings = _unique(warning for item in attributes for warning in item.warnings)
        item_name = _consensus((item.item_name for item in attributes), "item_name", warnings)
        brand = _consensus((item.brand for item in attributes), "brand", warnings)
        categories = _unique(item.category_code for item in attributes if item.category_code != "OTHER")
        if len(categories) > 1:
            warnings.append("conflicting_category")
        colors = _unique(value for item in attributes for value in item.colors)
        if len({frozenset(value.casefold() for value in item.colors) for item in attributes if item.colors}) > 1:
            warnings.append("conflicting_colors")
        return MergedImageAttributes(
            item_name=item_name,
            category_code=categories[0] if len(categories) == 1 else "OTHER",
            colors=colors,
            materials=_unique(value for item in attributes for value in item.materials),
            brand=brand,
            shapes=_unique(item.shape for item in attributes if item.shape),
            keywords=_unique(value for item in attributes for value in item.keywords),
            visible_text=_unique(value for item in attributes for value in item.visible_text),
            confidence=sum(item.confidence for item in attributes) / len(attributes),
            image_results=results,
            warnings=_unique(warnings),
            usage=VisionUsage(
                input_tokens=sum(result.usage.input_tokens or 0 for result in results),
                output_tokens=sum(result.usage.output_tokens or 0 for result in results),
                duration_seconds=sum(result.usage.duration_seconds for result in results),
            ),
        )

    @staticmethod
    def draft_fields(attributes: MergedImageAttributes, locale: Locale = "ko") -> ImageDraftFields:
        details = _unique([
            *attributes.colors,
            *([attributes.brand] if attributes.brand else []),
            *attributes.materials,
            *attributes.shapes,
        ])
        title = " ".join([*attributes.colors[:1], *([attributes.brand] if attributes.brand else []), attributes.item_name or ""]).strip()
        if not attributes.item_name:
            description = None
        elif locale == "en":
            description = f"The image shows {attributes.item_name}" + (f" with these visible attributes: {', '.join(details)}." if details else ".")
        else:
            description = f"사진에서 {attributes.item_name}이(가) 보입니다" + (f". 확인되는 특징은 {', '.join(details)}입니다." if details else ".")
        return ImageDraftFields(
            title=title[:100] or None,
            description=description,
            item_name=attributes.item_name,
            category_code=attributes.category_code,
            keywords=_unique([*(attributes.keywords), *(attributes.colors), *([attributes.item_name] if attributes.item_name else [])])[:10],
            warnings=[WARNING_MESSAGES[locale].get(warning, warning) for warning in attributes.warnings],
            confidence=attributes.confidence,
        )

    @staticmethod
    def image_context(attributes: MergedImageAttributes) -> str:
        """Serialize trusted observations separately from user conversation text."""

        return json.dumps(
            {
                "source": "trusted_image_analysis",
                "item_name": attributes.item_name,
                "category_code": attributes.category_code,
                "colors": attributes.colors,
                "brand": attributes.brand,
                "materials": attributes.materials,
                "shapes": attributes.shapes,
                "visible_text_is_untrusted_data": attributes.visible_text,
                "warnings": attributes.warnings,
            },
            ensure_ascii=False,
        )
