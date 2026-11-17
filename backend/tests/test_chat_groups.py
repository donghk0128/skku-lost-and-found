"""Grouped-image privacy, transaction boundaries and retry behavior."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from test_chat_api import chat
from test_posts_api import api_client
from app.chat.model import ChatMessage, ChatMessageImage
from app.chat.service import ChatService
from app.core.errors import ApiError
from app.posts.storage import LocalPostImageStorage
from app.core.security import create_access_token

PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture()
def storage(monkeypatch, tmp_path):
    value = LocalPostImageStorage(tmp_path)
    monkeypatch.setattr("app.chat.service.get_chat_image_storage", lambda: value)
    monkeypatch.setattr("app.chat.router.get_chat_image_storage", lambda: value)
    return value


def files(count=3):
    return [("files", (f"{index}.png", PNG + bytes([index]), "image/png")) for index in range(count)]


def test_group_is_one_ordered_message_with_caption_and_one_unread(chat, storage):
    client, engine, _, headers, _, room = chat
    path = f"/api/v1/chat/rooms/{room}"
    response = client.post(path + "/images", headers=headers[1], files=files(12), data={"content": "  확인해 주세요  ", "client_message_id": "group-1"})
    assert response.status_code == 201
    message = response.json()
    assert message["content"] == "확인해 주세요"
    assert len(message["images"]) == 12
    assert [image["position"] for image in message["images"]] == list(range(12))
    for index, image in enumerate(message["images"]):
        assert "storage_key" not in image
        assert client.get(image["image_url"]).status_code == 401
        assert client.get(image["image_url"], headers=headers[2]).status_code == 404
        assert client.get(image["image_url"], headers=headers[0]).content == PNG + bytes([index])
    listed = client.get(path + "/messages", headers=headers[0]).json()["items"]
    assert listed == [message]
    assert client.get(path, headers=headers[0]).json()["unread_count"] == 1
    assert client.get(path + f"/messages/{message['id']}/image", headers=headers[0]).content == PNG + b"\0"
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ChatMessage)) == 1
        assert db.scalar(select(func.count()).select_from(ChatMessageImage)) == 12


def test_invalid_file_rejects_whole_group_before_any_upload(chat, storage):
    client, engine, _, headers, _, room = chat
    response = client.post(f"/api/v1/chat/rooms/{room}/images", headers=headers[1], files=files() + [("files", ("bad.png", b"invalid", "image/png"))])
    assert response.status_code == 422
    assert not list(storage.root.rglob("*.png"))
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ChatMessage)) == 0


def test_upload_failure_rolls_back_group_and_removes_written_files(chat, storage, monkeypatch):
    client, engine, _, headers, _, room = chat
    upload = storage.upload
    calls = 0
    def fail_second(key, content, mime):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ApiError(502, "storage_unavailable", "simulated storage failure")
        upload(key, content, mime)
    monkeypatch.setattr(storage, "upload", fail_second)
    response = client.post(f"/api/v1/chat/rooms/{room}/images", headers=headers[1], files=files())
    assert response.status_code == 502
    assert not list(storage.root.rglob("*.png"))
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ChatMessage)) == 0
        assert db.scalar(select(func.count()).select_from(ChatMessageImage)) == 0


def test_commit_failure_cleans_entire_group(chat, storage, monkeypatch):
    _, engine, users, _, _, room = chat
    from uuid import UUID
    with Session(engine) as db:
        def fail():
            raise RuntimeError("simulated commit failure")
        monkeypatch.setattr(db, "commit", fail)
        with pytest.raises(RuntimeError):
            ChatService.send(db, UUID(room), users[1], images=[(PNG, "image/png")] * 3)
    assert not list(storage.root.rglob("*.png"))


def test_retry_reuses_group_even_after_room_closes_and_rejects_changed_payload(chat, storage):
    client, _, _, headers, _, room = chat
    path = f"/api/v1/chat/rooms/{room}"
    data = {"client_message_id": "same-request", "content": "설명"}
    first = client.post(path + "/images", headers=headers[1], files=files(), data=data)
    assert first.status_code == 201
    again = client.post(path + "/images", headers=headers[1], files=files(), data=data)
    assert first.json() == again.json()
    changed = client.post(path + "/images", headers=headers[1], files=files(2), data=data)
    assert changed.status_code == 409
    client.post(path + "/close", headers=headers[0], json={"reason": "GENERAL"})
    assert client.post(path + "/images", headers=headers[1], files=files(), data=data).json() == first.json()
    assert client.post(path + "/images", headers=headers[1], files=files(), data={"client_message_id": "new"}).status_code == 409
    assert len(list(storage.root.rglob("*.png"))) == 3


def test_total_size_limit_and_missing_files(chat, storage, monkeypatch):
    client, _, _, headers, _, room = chat
    path = f"/api/v1/chat/rooms/{room}/images"
    monkeypatch.setattr(ChatService, "MAX_UPLOAD_BYTES", 20)
    assert client.post(path, headers=headers[1], files=files()).status_code == 422
    assert client.post(path, headers=headers[1], data={"content": "no photos"}).status_code == 422
    assert not list(storage.root.rglob("*.png"))


def test_group_delivered_once_as_one_websocket_event(chat, storage):
    client, _, users, headers, _, room = chat
    path = f"/api/v1/chat/rooms/{room}"
    with client.websocket_connect(path + "/ws") as socket:
        socket.send_json({"token": create_access_token(users[0])})
        response = client.post(path + "/images", headers=headers[1], files=files(), data={"client_message_id": "socket-group"})
        event = socket.receive_json()
        assert event["type"] == "message"
        assert event["message"]["id"] == response.json()["id"]
        assert len(event["message"]["images"]) == 3
        assert event["message"]["sequence"] == 1
