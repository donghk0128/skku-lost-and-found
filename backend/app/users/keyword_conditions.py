"""Save and read keyword condition snapshots. No notification side effects."""

from datetime import datetime
from typing import Self
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
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
from app.users.model import KeywordCondition, User

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
