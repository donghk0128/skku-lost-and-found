"""Shared phrase/filter contract for browsing and saved keyword conditions."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator
from sqlalchemy import and_, func, or_

from app.posts.model import Post, PostLocation

MAX_FILTER_TERMS = 20
Phrase = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
LocationPhrase = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class PostFilterConditions(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    q: Phrase | None = None
    category_id: int | None = Field(default=None, ge=1)
    title_terms: list[Phrase] = Field(default_factory=list, max_length=MAX_FILTER_TERMS)
    content_terms: list[Phrase] = Field(default_factory=list, max_length=MAX_FILTER_TERMS)
    location_terms: list[LocationPhrase] = Field(default_factory=list, max_length=MAX_FILTER_TERMS)
    event_at: AwareDatetime | None = None

    @field_validator("title_terms", "content_terms", "location_terms")
    @classmethod
    def distinct_terms(cls, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result = []
        for value in values:
            if value.casefold() not in seen:
                seen.add(value.casefold())
                result.append(value)
        return result

    @field_validator("event_at")
    @classmethod
    def utc_event_at(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(timezone.utc) if value is not None else None

    def has_conditions(self) -> bool:
        return any((self.q, self.category_id, self.title_terms, self.content_terms, self.location_terms, self.event_at))


def read_post_filters(
    q: Phrase | None = Query(default=None),
    category_id: int | None = Query(default=None, ge=1),
    title_terms: list[Phrase] | None = Query(default=None, max_length=MAX_FILTER_TERMS),
    content_terms: list[Phrase] | None = Query(default=None, max_length=MAX_FILTER_TERMS),
    location_terms: list[LocationPhrase] | None = Query(default=None, max_length=MAX_FILTER_TERMS),
    event_at: AwareDatetime | None = Query(default=None),
) -> PostFilterConditions:
    return PostFilterConditions(
        q=q, category_id=category_id, title_terms=title_terms or [], content_terms=content_terms or [],
        location_terms=location_terms or [], event_at=event_at,
    )


def contains_phrase(column, phrase: str):
    # Preserve internal spaces and escape SQL LIKE metacharacters as literal text.
    return func.lower(func.coalesce(column, "")).contains(phrase.lower(), autoescape=True)


def post_filter_expressions(conditions: PostFilterConditions) -> list:
    """AND between fields; OR between phrases in a field. Never join/duplicate posts."""
    expressions = []
    if conditions.q:
        expressions.append(or_(*(contains_phrase(column, conditions.q) for column in (
            Post.title, Post.description, Post.item_name,
        ))))
    if conditions.category_id is not None:
        expressions.append(Post.category_id == conditions.category_id)
    for column, terms in ((Post.title, conditions.title_terms), (Post.description, conditions.content_terms)):
        if terms:
            expressions.append(or_(*(contains_phrase(column, term) for term in terms)))
    if conditions.location_terms:
        expressions.append(or_(
            Post.locations.any(or_(*(contains_phrase(PostLocation.location_text, term) for term in conditions.location_terms))),
            and_(~Post.locations.any(), or_(*(contains_phrase(Post.location_text, term) for term in conditions.location_terms))),
        ))
    if conditions.event_at is not None:
        expressions.extend((Post.event_start_at <= conditions.event_at, Post.event_end_at >= conditions.event_at))
    return expressions
