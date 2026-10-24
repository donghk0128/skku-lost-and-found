"""Business rules for creating, reading, updating, and deleting posts."""

from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.posts.model import Category, Post, PostImage, now_utc
from app.posts.repository import PostRepository
from app.posts.schemas import PostCreateRequest, PostStatus, PostType, PostUpdateRequest
from app.posts.storage import get_post_image_storage
from app.users.model import User


class PostService:
    IMAGE_TYPES = {
        "image/jpeg": (".jpg", lambda data: data.startswith(b"\xff\xd8\xff")),
        "image/png": (".png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
        "image/webp": (".webp", lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP"),
    }
    MAX_IMAGE_BYTES = 5 * 1024 * 1024
    MAX_IMAGES_PER_POST = 5

    @staticmethod
    def upload_image(db: Session, post_id: UUID, author: User, content: bytes, content_type: str) -> PostImage:
        PostService._get_owned_post(db, post_id, author)
        if not content or len(content) > PostService.MAX_IMAGE_BYTES:
            raise ApiError(422, "invalid_image_size", "사진은 1바이트 이상 5MiB 이하여야 합니다.")
        image_type = PostService.IMAGE_TYPES.get(content_type)
        if image_type is None or not image_type[1](content):
            raise ApiError(422, "invalid_image_type", "JPEG, PNG, WebP 사진만 업로드할 수 있습니다.")
        existing = PostRepository.list_images(db, post_id)
        if len(existing) >= PostService.MAX_IMAGES_PER_POST:
            raise ApiError(422, "image_limit", "게시글에는 사진을 최대 5장까지 올릴 수 있습니다.")
        extension = image_type[0]
        image = PostImage(
            post_id=post_id,
            storage_key=f"{post_id}/{uuid4()}{extension}",
            content_type=content_type,
            position=len(existing),
        )
        storage = get_post_image_storage()
        storage.upload(image.storage_key, content, content_type)
        try:
            PostRepository.add_image(db, image)
            PostService._commit(db)
        except SQLAlchemyError:
            try:
                storage.delete(image.storage_key)
            except ApiError:
                pass
            raise
        db.refresh(image)
        return image

    @staticmethod
    def list_images(db: Session, post_id: UUID) -> list[PostImage]:
        PostService.get_visible_by_id(db, post_id)
        return PostRepository.list_images(db, post_id)

    @staticmethod
    def get_image_content(db: Session, post_id: UUID, image_id: UUID) -> tuple[bytes, str]:
        PostService.get_visible_by_id(db, post_id)
        image = PostRepository.get_image(db, post_id, image_id)
        if image is None:
            raise ApiError(404, "post_image_not_found", "사진을 찾을 수 없습니다.")
        return get_post_image_storage().download(image.storage_key), image.content_type

    @staticmethod
    def create(db: Session, request: PostCreateRequest, author: User) -> Post:
        PostService._require_category(db, request.category_id)
        post = Post(
            author_id=author.id,
            post_type=request.post_type,
            title=request.title,
            description=request.description,
            item_name=request.item_name,
            category_id=request.category_id,
            location_text=request.location_text,
            latitude=request.latitude,
            longitude=request.longitude,
            event_start_at=request.event_start_at,
            event_end_at=request.event_end_at,
        )
        PostRepository.create(db, post)
        PostService._commit(db)
        db.refresh(post)
        return post

    @staticmethod
    def get_visible_by_id(db: Session, post_id: UUID) -> Post:
        post = PostRepository.get_visible_by_id(db, post_id)
        if post is None:
            raise ApiError(404, "post_not_found", "게시글을 찾을 수 없습니다.")
        return post

    @staticmethod
    def list_visible(
        db: Session,
        post_type: PostType | None,
        category_id: int | None,
        post_status: PostStatus | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Post], int]:
        if search is not None:
            search = search.strip()
            if not search:
                raise ApiError(422, "invalid_search_query", "검색어를 입력해 주세요.")
        return PostRepository.list_visible(db, post_type, category_id, post_status, search, limit, offset)

    @staticmethod
    def list_categories(db: Session) -> list[Category]:
        return PostRepository.list_categories(db)

    @staticmethod
    def update(db: Session, post_id: UUID, request: PostUpdateRequest, author: User) -> Post:
        post = PostService._get_owned_post(db, post_id, author)
        if "category_id" in request.model_fields_set:
            PostService._require_category(db, request.category_id)
        PostRepository.update_details(post, request.model_dump(exclude_unset=True))
        PostService._commit(db)
        db.refresh(post)
        return post

    @staticmethod
    def complete(db: Session, post_id: UUID, author: User) -> Post:
        post = PostService._get_owned_post(db, post_id, author)
        if post.status != "COMPLETED":
            PostRepository.mark_completed(post)
            PostService._commit(db)
            db.refresh(post)
        return post

    @staticmethod
    def delete(db: Session, post_id: UUID, author: User) -> None:
        post = PostService._get_owned_post(db, post_id, author)
        PostRepository.mark_deleted(post, now_utc())
        PostService._commit(db)

    @staticmethod
    def _get_owned_post(db: Session, post_id: UUID, author: User) -> Post:
        post = PostService.get_visible_by_id(db, post_id)
        if post.author_id != author.id:
            raise ApiError(403, "post_forbidden", "본인이 작성한 게시글만 변경할 수 있습니다.")
        return post

    @staticmethod
    def _require_category(db: Session, category_id: int | None) -> None:
        if category_id is not None and PostRepository.get_category_by_id(db, category_id) is None:
            raise ApiError(422, "category_not_found", "선택한 카테고리가 존재하지 않습니다.")

    @staticmethod
    def _commit(db: Session) -> None:
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise
