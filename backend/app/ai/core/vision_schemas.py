"""Provider-independent contracts for structured image analysis."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .schemas import CategoryCode


class ImageAttributes(BaseModel):
    """Observable lost-item attributes extracted from one image."""

    model_config = ConfigDict(extra="forbid")

    item_name: Optional[str] = Field(default=None, max_length=100)
    category_code: CategoryCode
    colors: list[str] = Field(default_factory=list, max_length=10)
    materials: list[str] = Field(default_factory=list, max_length=10)
    brand: Optional[str] = Field(default=None, max_length=100)
    shape: Optional[str] = Field(default=None, max_length=100)
    keywords: list[str] = Field(default_factory=list, max_length=15)
    visible_text: list[str] = Field(default_factory=list, max_length=10)
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("colors", "materials", "keywords", "visible_text", "warnings")
    @classmethod
    def normalize_list(cls, values: list[str]) -> list[str]:
        """Remove blank and duplicate values while preserving order."""
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class VisionUsage(BaseModel):
    """Comparable image-analysis telemetry."""

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    duration_seconds: float


class VisionResult(BaseModel):
    """Validated image attributes with provider metadata."""

    attributes: ImageAttributes
    usage: VisionUsage
    provider: str
    model: str


def vision_json_schema() -> dict:
    """Return a strict JSON schema accepted by both providers."""
    schema = ImageAttributes.model_json_schema()

    def normalize(node: object) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                node["required"] = list(properties)
                node["additionalProperties"] = False
            for value in node.values():
                normalize(value)
        elif isinstance(node, list):
            for value in node:
                normalize(value)

    normalize(schema)
    return schema
