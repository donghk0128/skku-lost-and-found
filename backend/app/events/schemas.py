from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


ClientEventType = Literal["screen_view", "post_view", "search_applied", "filter_applied", "recommendation_impression", "recommendation_click"]
Screen = Literal["home", "post_detail", "chat", "my_posts", "create_post"]


class EventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    event_type: ClientEventType
    occurred_at: AwareDatetime
    visit_id: UUID | None = None
    screen: Screen | None = None
    post_id: UUID | None = None
    source_post_id: UUID | None = None
    candidate_post_id: UUID | None = None
    run_id: UUID | None = None
    rank: int | None = Field(default=None, ge=1)
    category_id: int | None = Field(default=None, ge=1)
    has_query: bool | None = None
    has_title_terms: bool | None = None
    has_content_terms: bool | None = None
    has_location_terms: bool | None = None
    has_event_time: bool | None = None

    @model_validator(mode="after")
    def valid_context(self):
        if self.event_type == "screen_view" and (self.screen is None or self.visit_id is None):
            raise ValueError("screen and visit_id are required")
        if self.event_type == "post_view" and (self.post_id is None or self.visit_id is None):
            raise ValueError("post_id and visit_id are required")
        if self.event_type in ("recommendation_impression", "recommendation_click") and (
            self.visit_id is None or self.run_id is None or self.source_post_id is None
            or self.candidate_post_id is None or self.rank is None
        ):
            raise ValueError("recommendation context is required")
        return self


class EventAccepted(BaseModel):
    event_id: UUID
    accepted: bool
