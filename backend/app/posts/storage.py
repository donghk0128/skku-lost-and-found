"""Store image bytes using provider-neutral keys from the post_images table."""

from pathlib import Path
from uuid import UUID

from app.core.config import get_settings
from app.core.errors import ApiError


class LocalPostImageStorage:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or Path(get_settings().post_image_dir)).resolve()

    def _path(self, storage_key: str) -> Path:
        parts = storage_key.split("/")
        if len(parts) != 2 or "\\" in storage_key:
            raise ApiError(500, "invalid_storage_key", "사진 저장 경로가 올바르지 않습니다.")
        try:
            UUID(parts[0])
            UUID(parts[1].rsplit(".", 1)[0])
        except (ValueError, IndexError) as error:
            raise ApiError(500, "invalid_storage_key", "사진 저장 경로가 올바르지 않습니다.") from error
        if not parts[1].endswith((".jpg", ".png", ".webp")):
            raise ApiError(500, "invalid_storage_key", "사진 저장 경로가 올바르지 않습니다.")
        path = (self.root / parts[0] / parts[1]).resolve()
        if not path.is_relative_to(self.root):
            raise ApiError(500, "invalid_storage_key", "사진 저장 경로가 올바르지 않습니다.")
        return path

    def upload(self, storage_key: str, content: bytes, content_type: str) -> None:
        path = self._path(storage_key)
        created = False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as file:
                created = True
                file.write(content)
        except FileExistsError as error:
            raise ApiError(409, "image_exists", "사진 경로가 이미 사용 중입니다.") from error
        except OSError as error:
            if created:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise ApiError(502, "storage_unavailable", "사진 저장에 실패했습니다.") from error

    def download(self, storage_key: str) -> bytes:
        path = self._path(storage_key)
        try:
            return path.read_bytes()
        except FileNotFoundError as error:
            raise ApiError(404, "post_image_not_found", "사진 파일을 찾을 수 없습니다.") from error
        except OSError as error:
            raise ApiError(502, "storage_unavailable", "사진을 읽을 수 없습니다.") from error

    def delete(self, storage_key: str) -> None:
        path = self._path(storage_key)
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            raise ApiError(502, "storage_unavailable", "사진 삭제에 실패했습니다.") from error


def get_post_image_storage() -> LocalPostImageStorage:
    return LocalPostImageStorage()
