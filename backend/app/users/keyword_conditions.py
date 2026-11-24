"""Account-owned filter snapshots and explicit notification opt-in."""

from datetime import datetime
from typing import Self
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, ConfigDict, model_validator
from pydantic_core import PydanticCustomError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.service import get_current_user
from app.core.database import get_db
from app.core.errors import ApiError
from app.posts.filters import PostFilterConditions
from app.posts.model import Category
from app.posts.schemas import PostType
from app.users.model import KeywordCondition, User, now_utc

router = APIRouter(prefix="/users/me/keyword-conditions", tags=["keyword-conditions"])


class KeywordConditionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    post_type: PostType
    conditions: PostFilterConditions

    @model_validator(mode="after")
    def require_condition(self) -> Self:
        if not self.conditions.has_conditions():
            raise PydanticCustomError("keyword_condition_empty", "저장할 조건을 하나 이상 입력해 주세요.")
        return self


class KeywordConditionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_type: PostType
    version: int
    conditions: PostFilterConditions
    notification_enabled: bool
    created_at: datetime


class KeywordConditionListResponse(BaseModel):
    items: list[KeywordConditionResponse]
    total: int
    limit: int
    offset: int


@router.post("", response_model=KeywordConditionResponse, status_code=status.HTTP_201_CREATED)
def save_keyword_condition(
    request: KeywordConditionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> KeywordCondition:
    if request.conditions.category_id is not None and db.get(Category, request.conditions.category_id) is None:
        raise ApiError(422, "category_not_found", "선택한 카테고리가 존재하지 않습니다.")
    row = KeywordCondition(user_id=user.id, post_type=request.post_type, conditions=request.conditions.model_dump(mode="json"))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=KeywordConditionListResponse)
def list_keyword_conditions(
    limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> KeywordConditionListResponse:
    owned = KeywordCondition.user_id == user.id
    total = db.scalar(select(func.count()).select_from(KeywordCondition).where(owned)) or 0
    items = db.scalars(select(KeywordCondition).where(owned)
        .order_by(KeywordCondition.created_at.desc(), KeywordCondition.id.desc()).offset(offset).limit(limit)).all()
    return KeywordConditionListResponse(items=items, total=total, limit=limit, offset=offset)


class KeywordConditionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notification_enabled: bool


def owned_condition(db: Session, user: User, condition_id: UUID) -> KeywordCondition:
    row = db.scalar(select(KeywordCondition).where(
        KeywordCondition.id == condition_id, KeywordCondition.user_id == user.id,
    ).with_for_update())
    if row is None:
        raise ApiError(404, "keyword_condition_not_found", "저장한 조건을 찾을 수 없습니다.")
    return row


@router.patch("/{condition_id}", response_model=KeywordConditionResponse)
def update_keyword_condition(
    condition_id: UUID, request: KeywordConditionUpdate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> KeywordCondition:
    row = owned_condition(db, user, condition_id)
    if request.notification_enabled and not row.notification_enabled:
        row.notification_enabled_at = now_utc()
    row.notification_enabled = request.notification_enabled
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{condition_id}", status_code=204)
def delete_keyword_condition(
    condition_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> Response:
    db.delete(owned_condition(db, user, condition_id))
    db.commit()
    return Response(status_code=204)
