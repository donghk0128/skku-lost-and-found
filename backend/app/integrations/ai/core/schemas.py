"""Provider-independent data contracts for AI post drafting."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


PostType = Literal["LOST", "FOUND"]
CategoryCode = Literal[
    "ELECTRONICS",
    "WALLET",
    "ID_CARD",
    "BAG",
    "CLOTHING",
    "KEY",
    "BOOK_STATIONERY",
    "OTHER",
]
MissingField = Literal["item_name", "location", "event_time"]

CATEGORY_LABELS: dict[str, str] = {
    "ELECTRONICS": "전자기기",
    "WALLET": "지갑",
    "ID_CARD": "신분증·카드",
    "BAG": "가방",
    "CLOTHING": "의류·잡화",
    "KEY": "열쇠",
    "BOOK_STATIONERY": "도서·문구",
    "OTHER": "기타",
}


class DraftRequest(BaseModel):
    """Natural-language report supplied to a model."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    post_type: PostType
    natural_language: str = Field(min_length=1, max_length=4000)
    reference_time: AwareDatetime


class PostDraft(BaseModel):
    """Editable structured post draft shared by every provider."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=4000)
    item_name: Optional[str] = Field(default=None, max_length=100)
    category_code: CategoryCode
    location_text: Optional[str] = Field(default=None, max_length=255)
    event_start_at: Optional[AwareDatetime] = None
    event_end_at: Optional[AwareDatetime] = None
    keywords: list[str] = Field(default_factory=list, max_length=10)
    missing_fields: list[MissingField] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_time_pair(self) -> "PostDraft":
        if (self.event_start_at is None) != (self.event_end_at is None):
            raise ValueError("event_start_at and event_end_at must both be set or both be null")
        if self.event_start_at and self.event_end_at and self.event_start_at > self.event_end_at:
            raise ValueError("event_start_at must not be later than event_end_at")
        self.keywords = list(dict.fromkeys(value.strip() for value in self.keywords if value.strip()))[:10]
        return self


class Usage(BaseModel):
    """Comparable request telemetry without user content."""

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    duration_seconds: float


class GenerationResult(BaseModel):
    """Validated draft with provider metadata."""

    draft: PostDraft
    usage: Usage
    provider: str
    model: str


class GoldCase(BaseModel):
    """One labeled baseline evaluation example."""

    id: str
    request: DraftRequest
    expected: PostDraft


def parse_optional_datetime(value: str) -> Optional[datetime]:
    """Parse an optional ISO 8601 value used by the Streamlit editor."""

    stripped = value.strip()
    return datetime.fromisoformat(stripped) if stripped else None


def strict_json_schema() -> dict:
    """Return the draft schema with every property required for strict APIs."""

    schema = PostDraft.model_json_schema()

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
