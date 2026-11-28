"""Validate and merge in-memory image analysis results."""

import json
import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

from .providers import ProviderError
from .schemas import Locale
from .vision_providers import VisionProvider
from .vision_schemas import (
    MAX_IMAGE_BYTES,
    MAX_IMAGE_COUNT,
    ImageAttributes,
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
        "partial_image_analysis_failure": "일부 사진을 분석하지 못해 성공한 사진만 반영했습니다.",
    },
    "en": {
        "conflicting_item_name": "The item was identified differently across photos.",
        "conflicting_brand": "The brand was identified differently across photos.",
        "conflicting_category": "The category was identified differently across photos.",
        "conflicting_colors": "The colors were identified differently across photos.",
        "partial_image_analysis_failure": "Some photos could not be analyzed, so only successful results were used.",
    },
}

NAME_STOP_WORDS = {"a", "an", "and", "for", "in", "of", "on", "the", "with"}


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


def _name_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[^\W_]+", value.casefold())
        if token not in NAME_STOP_WORDS
        and (len(token) > 1 or any("가" <= character <= "힣" for character in token))
    }


def _names_related(left: str, right: str) -> bool:
    compact_left = "".join(re.findall(r"[^\W_]+", left.casefold()))
    compact_right = "".join(re.findall(r"[^\W_]+", right.casefold()))
    return (
        compact_left == compact_right
        or bool(compact_left and compact_right and (compact_left in compact_right or compact_right in compact_left))
        or bool(_name_tokens(left) & _name_tokens(right))
    )


def _select_item_group(
    attributes: list[ImageAttributes], warnings: list[str]
) -> tuple[str | None, list[ImageAttributes]]:
    named = [(index, item) for index, item in enumerate(attributes) if item.item_name]
    if not named:
        return None, attributes

    remaining = set(range(len(named)))
    groups: list[list[tuple[int, ImageAttributes]]] = []
    while remaining:
        pending = [remaining.pop()]
        group: list[tuple[int, ImageAttributes]] = []
        while pending:
            position = pending.pop()
            candidate = named[position]
            group.append(candidate)
            related = {
                other
                for other in remaining
                if _names_related(candidate[1].item_name or "", named[other][1].item_name or "")
            }
            remaining -= related
            pending.extend(related)
        groups.append(group)

    selected = max(
        groups,
        key=lambda group: (sum(item.confidence for _, item in group), len(group), -min(index for index, _ in group)),
    )
    if len(groups) > 1:
        warnings.append("conflicting_item_name")

    selected_indices = {index for index, _ in selected}
    selected_categories = {
        item.category_code for _, item in selected if item.category_code != "OTHER"
    }
    for index, item in enumerate(attributes):
        if item.item_name is None and (
            not selected_categories or item.category_code in selected_categories or item.category_code == "OTHER"
        ):
            selected_indices.add(index)

    representative = min(
        selected,
        key=lambda entry: (
            -entry[1].confidence,
            len((entry[1].item_name or "").split()),
            len(entry[1].item_name or ""),
            entry[0],
        ),
    )[1].item_name
    return representative, [item for index, item in enumerate(attributes) if index in selected_indices]


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

        def analyze_image(image: ImageInput) -> VisionResult | ProviderError:
            try:
                return self.provider.analyze(image.content, image.mime_type, locale)
            except ProviderError as error:
                return error

        worker_count = min(max(1, max_workers), len(images))
        if worker_count == 1:
            outcomes = [analyze_image(image) for image in images]
        else:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                outcomes = list(executor.map(analyze_image, images))
        failures = [outcome for outcome in outcomes if isinstance(outcome, ProviderError)]
        results = [outcome for outcome in outcomes if isinstance(outcome, VisionResult)]
        if not results:
            raise failures[0]

        attributes = [result.attributes for result in results]
        warnings = _unique(warning for item in attributes for warning in item.warnings)
        if failures:
            warnings.append("partial_image_analysis_failure")
        item_name, selected_attributes = _select_item_group(attributes, warnings)
        brand = _consensus((item.brand for item in selected_attributes), "brand", warnings)
        categories = _unique(item.category_code for item in selected_attributes if item.category_code != "OTHER")
        if len(categories) > 1:
            warnings.append("conflicting_category")
        colors = _unique(value for item in selected_attributes for value in item.colors)
        if len({frozenset(value.casefold() for value in item.colors) for item in selected_attributes if item.colors}) > 1:
            warnings.append("conflicting_colors")
        return MergedImageAttributes(
            item_name=item_name,
            category_code=categories[0] if len(categories) == 1 else "OTHER",
            colors=colors,
            materials=_unique(value for item in selected_attributes for value in item.materials),
            brand=brand,
            shapes=_unique(item.shape for item in selected_attributes if item.shape),
            keywords=_unique(value for item in selected_attributes for value in item.keywords),
            visible_text=_unique(value for item in selected_attributes for value in item.visible_text),
            confidence=sum(item.confidence for item in selected_attributes) / len(selected_attributes),
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
