"""Check that the local image store preserves bytes and rejects unsafe keys."""

from uuid import uuid4

import pytest

from app.core.errors import ApiError
from app.posts.storage import LocalPostImageStorage


def test_image_survives_new_storage_instance(tmp_path) -> None:
    key = f"{uuid4()}/{uuid4()}.png"
    first = LocalPostImageStorage(tmp_path)
    first.upload(key, b"image bytes", "image/png")

    second = LocalPostImageStorage(tmp_path)
    assert second.download(key) == b"image bytes"

    second.delete(key)
    with pytest.raises(ApiError) as error:
        first.download(key)
    assert error.value.status_code == 404


@pytest.mark.parametrize("key", ["../outside.png", "not-a-uuid/file.png", "folder/../../outside.png"])
def test_image_store_rejects_unsafe_keys(tmp_path, key: str) -> None:
    storage = LocalPostImageStorage(tmp_path)
    with pytest.raises(ApiError) as error:
        storage.upload(key, b"image bytes", "image/png")
    assert error.value.status_code == 500
