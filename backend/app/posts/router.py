"""HTTP endpoints for posts."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.service import get_current_user
from app.core.database import get_db
from app.posts.model import Category, Post, PostImage
from app.posts.schemas import CategoryResponse, PostCreateRequest, PostImageResponse, PostListResponse, PostResponse, PostStatus, PostStatusUpdateRequest, PostType, PostUpdateRequest
from app.posts.service import PostService
from app.users.model import User


router = APIRouter(prefix="/posts", tags=["posts"])
categories_router = APIRouter(prefix="/categories", tags=["categories"])


@categories_router.get("", response_model=list[CategoryResponse])
def list_categories(db: Session = Depends(get_db)) -> list[Category]:
    return PostService.list_categories(db)


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    request: PostCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Post:
    return PostService.create(db, request, current_user)


@router.get("", response_model=PostListResponse)
def list_posts(
    post_type: PostType | None = None,
    category_id: int | None = Query(default=None, ge=1),
    status: PostStatus | None = None,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> PostListResponse:
    posts, total = PostService.list_visible(db, post_type, category_id, status, q, limit, offset)
    return PostListResponse(items=posts, total=total, limit=limit, offset=offset)


@router.get("/{post_id}", response_model=PostResponse)
def get_post(post_id: UUID, db: Session = Depends(get_db)) -> Post:
    return PostService.get_visible_by_id(db, post_id)


@router.patch("/{post_id}", response_model=PostResponse)
def update_post(
    post_id: UUID,
    request: PostUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Post:
    return PostService.update(db, post_id, request, current_user)


@router.patch("/{post_id}/status", response_model=PostResponse)
def complete_post(
    post_id: UUID,
    request: PostStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Post:
    return PostService.complete(db, post_id, current_user)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    PostService.delete(db, post_id, current_user)


def image_response(image: PostImage) -> PostImageResponse:
    return PostImageResponse(
        id=image.id,
        post_id=image.post_id,
        content_type=image.content_type,
        position=image.position,
        created_at=image.created_at,
        content_url=f"/api/v1/posts/{image.post_id}/images/{image.id}/content",
    )


@router.post("/{post_id}/images", response_model=PostImageResponse, status_code=status.HTTP_201_CREATED)
def upload_post_image(
    post_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostImageResponse:
    content = file.file.read(PostService.MAX_IMAGE_BYTES + 1)
    image = PostService.upload_image(db, post_id, current_user, content, file.content_type or "")
    return image_response(image)


@router.get("/{post_id}/images", response_model=list[PostImageResponse])
def list_post_images(post_id: UUID, db: Session = Depends(get_db)) -> list[PostImageResponse]:
    return [image_response(image) for image in PostService.list_images(db, post_id)]


@router.get("/{post_id}/images/{image_id}/content")
def get_post_image_content(post_id: UUID, image_id: UUID, db: Session = Depends(get_db)) -> Response:
    content, content_type = PostService.get_image_content(db, post_id, image_id)
    return Response(content=content, media_type=content_type)
