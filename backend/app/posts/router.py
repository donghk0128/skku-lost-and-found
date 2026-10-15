"""HTTP endpoints for posts."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.service import get_current_user
from app.core.database import get_db
from app.posts.model import Post
from app.posts.schemas import PostCreateRequest, PostResponse
from app.posts.service import PostService
from app.users.model import User


router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    request: PostCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Post:
    return PostService.create(db, request, current_user)


@router.get("/{post_id}", response_model=PostResponse)
def get_post(post_id: UUID, db: Session = Depends(get_db)) -> Post:
    return PostService.get_visible_by_id(db, post_id)
