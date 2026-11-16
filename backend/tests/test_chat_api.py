"""Exercise chat privacy, lifecycle and transport through the public API."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from starlette.websockets import WebSocketDisconnect

from test_posts_api import api_client, create_author
from app.core.security import create_access_token, create_refresh_token, _create_token
from app.chat.model import ChatRoomMember
from app.chat.service import ChatService
from app.core.errors import ApiError
from sqlalchemy.orm import Session


@pytest.fixture()
def chat(api_client):
    client, engine = api_client
    users = [create_author(engine, f"chat-{i}@skku.edu") for i in range(4)]
    headers = [{"Authorization": f"Bearer {create_access_token(uid)}"} for uid in users]
    post = client.post("/api/v1/posts", headers=headers[0], json={
        "post_type": "FOUND", "title": "습득", "description": "검정 지갑",
    }).json()
    room = client.post("/api/v1/chat/rooms", headers=headers[1], json={"post_id": post["id"]})
    assert room.status_code == 200
    return client, engine, users, headers, post["id"], room.json()["id"]


def test_room_creation_is_idempotent_and_private(chat):
    client, engine, users, headers, post, room = chat
    path = "/api/v1/chat/rooms"
    assert client.post(path, json={"post_id": post}).status_code == 401
    assert client.post(path, headers=headers[0], json={"post_id": post}).status_code == 422
    assert client.post(path, headers=headers[1], json={"post_id": str(uuid4())}).status_code == 404
    assert client.post(path, headers=headers[1], json={"post_id": post}).json()["id"] == room
    assert client.get(path, headers=headers[0]).json()["total"] == 1
    assert client.get(path, headers=headers[2]).json()["total"] == 0
    for suffix in ("", "/messages"):
        assert client.get(f"{path}/{room}{suffix}", headers=headers[2]).status_code == 404
    assert client.post(f"{path}/{room}/messages", headers=headers[2], json={"content": "no"}).status_code == 404
    assert client.post(f"{path}/{room}/close", headers=headers[2], json={"reason": "GENERAL"}).status_code == 404
    with Session(engine) as db:
        assert db.get(ChatRoomMember, (UUID(room), users[0])) is not None
        assert db.get(ChatRoomMember, (UUID(room), users[1])) is not None


def test_messages_pagination_and_monotonic_read(chat):
    client, _, _, headers, _, room = chat
    path = f"/api/v1/chat/rooms/{room}"
    for body in ({"content": " "}, {"content": "x" * 2001}, {"content": "hi", "sender_id": str(uuid4())}):
        assert client.post(path + "/messages", headers=headers[1], json=body).status_code == 422
    for index in range(3):
        response = client.post(path + "/messages", headers=headers[1], json={"content": f" {index} "})
        assert response.status_code == 201
        assert response.json()["sequence"] == index + 1
        assert response.json()["content"] == str(index)
    assert client.get(path, headers=headers[0]).json()["unread_count"] == 3
    assert client.get(path, headers=headers[1]).json()["unread_count"] == 0
    first = client.get(path + "/messages?limit=2", headers=headers[0]).json()
    assert [m["sequence"] for m in first["items"]] == [1, 2]
    assert first["has_more"] and first["next_after"] == 2
    second = client.get(path + "/messages?after=2", headers=headers[0]).json()
    assert [m["sequence"] for m in second["items"]] == [3]
    assert not second["has_more"]
    read = client.patch(path + "/read", headers=headers[0], json={"sequence": 2})
    assert read.json()["unread_count"] == 1
    assert read.json()["last_read_at"] is not None
    assert client.patch(path + "/read", headers=headers[0], json={"sequence": 1}).json()["last_read_sequence"] == 2
    assert client.patch(path + "/read", headers=headers[0], json={"sequence": 4}).status_code == 422


def test_general_close_delete_guard_and_personal_hide(chat):
    client, _, _, headers, post, room = chat
    path = f"/api/v1/chat/rooms/{room}"
    assert client.delete(f"/api/v1/posts/{post}", headers=headers[0]).status_code == 409
    assert client.patch(path + "/visibility", headers=headers[1], json={"is_hidden": True}).status_code == 409
    closed = client.post(path + "/close", headers=headers[1], json={"reason": "GENERAL"})
    assert closed.json()["status"] == "CLOSED"
    existing = client.post("/api/v1/chat/rooms", headers=headers[1], json={"post_id": post})
    assert existing.json()["id"] == room and existing.json()["status"] == "CLOSED"
    assert client.get(f"/api/v1/posts/{post}").json()["status"] == "OPEN"
    assert client.post(path + "/close", headers=headers[1], json={"reason": "GENERAL"}).status_code == 200
    assert client.post(path + "/close", headers=headers[1], json={"reason": "RETURNED"}).status_code == 409
    assert client.post(path + "/messages", headers=headers[0], json={"content": "closed"}).status_code == 409
    assert client.patch(path + "/visibility", headers=headers[1], json={"is_hidden": True}).status_code == 200
    assert client.get("/api/v1/chat/rooms", headers=headers[1]).json()["total"] == 0
    assert client.get("/api/v1/chat/rooms?include_hidden=true", headers=headers[1]).json()["total"] == 1
    assert client.get("/api/v1/chat/rooms", headers=headers[0]).json()["total"] == 1
    assert client.delete(f"/api/v1/posts/{post}", headers=headers[0]).status_code == 204
    assert client.get(path, headers=headers[1]).status_code == 200
    assert client.post("/api/v1/chat/rooms", headers=headers[2], json={"post_id": post}).status_code == 404


@pytest.mark.parametrize("via_post", [False, True])
def test_completion_closes_all_rooms_atomically(chat, via_post):
    client, _, _, headers, post, room = chat
    second = client.post("/api/v1/chat/rooms", headers=headers[2], json={"post_id": post}).json()["id"]
    if via_post:
        result = client.patch(f"/api/v1/posts/{post}/status", headers=headers[0], json={"status": "COMPLETED"})
    else:
        result = client.post(f"/api/v1/chat/rooms/{room}/close", headers=headers[1], json={"reason": "RETURNED"})
    assert result.status_code == 200
    assert client.get(f"/api/v1/posts/{post}").json()["status"] == "COMPLETED"
    first = client.get(f"/api/v1/chat/rooms/{room}", headers=headers[0]).json()
    assert first["close_reason"] == ("POST_COMPLETED" if via_post else "RETURNED")
    assert client.get(f"/api/v1/chat/rooms/{second}", headers=headers[2]).json()["close_reason"] == "POST_COMPLETED"
    assert client.post("/api/v1/chat/rooms", headers=headers[3], json={"post_id": post}).status_code == 409
    assert client.post(f"/api/v1/chat/rooms/{second}/messages", headers=headers[2], json={"content": "no"}).status_code == 409


def test_private_image_message_validation_and_retention(chat, monkeypatch, tmp_path):
    from app.posts.storage import LocalPostImageStorage
    monkeypatch.setattr("app.chat.service.get_chat_image_storage", lambda: LocalPostImageStorage(tmp_path))
    monkeypatch.setattr("app.chat.router.get_chat_image_storage", lambda: LocalPostImageStorage(tmp_path))
    client, _, _, headers, post, room = chat
    path = f"/api/v1/chat/rooms/{room}"
    image = b"\x89PNG\r\n\x1a\n" + b"test"
    for data, mime in [(b"fake", "image/png"), (image, "text/plain"), (b"x" * (5 * 1024 * 1024 + 1), "image/png")]:
        assert client.post(path + "/images", headers=headers[1], files={"file": ("x.png", data, mime)}).status_code == 422
    result = client.post(path + "/images", headers=headers[1], files={"file": ("x.png", image, "image/png")})
    assert result.status_code == 201
    message = result.json()
    assert message["message_type"] == "IMAGE" and message["content"] is None
    assert "image_storage_key" not in message
    url = message["image_url"]
    assert client.get(url).status_code == 401
    assert client.get(url, headers=headers[2]).status_code == 404
    assert client.get(url, headers=headers[0]).content == image
    client.post(path + "/close", headers=headers[1], json={"reason": "GENERAL"})
    client.delete(f"/api/v1/posts/{post}", headers=headers[0])
    assert client.get(url, headers=headers[0]).content == image


def test_image_cleanup_on_failed_database_commit(chat, monkeypatch, tmp_path):
    from app.posts.storage import LocalPostImageStorage
    monkeypatch.setattr("app.chat.service.get_chat_image_storage", lambda: LocalPostImageStorage(tmp_path))
    _, engine, users, _, _, room = chat
    with Session(engine) as db:
        def fail():
            raise RuntimeError("simulated commit failure")
        monkeypatch.setattr(db, "commit", fail)
        with pytest.raises(RuntimeError):
            ChatService.send(db, UUID(room), users[1], image=b"\x89PNG\r\n\x1a\n", content_type="image/png")
    assert not list(tmp_path.rglob("*.png"))


def test_websocket_send_resume_receive_and_room_close(chat):
    client, _, users, headers, _, room = chat
    path = f"/api/v1/chat/rooms/{room}"
    token = create_access_token(users[0])
    with client.websocket_connect(path + "/ws") as ws:
        ws.send_json({"token": token})
        ws.send_json({"content": "   "})
        assert ws.receive_json()["error"]["code"] == "validation_error"
        ws.send_json({"content": "안녕하세요"})
        own = ws.receive_json()
        assert own["message"]["sequence"] == 1
        client.post(path + "/messages", headers=headers[1], json={"content": "네"})
        assert ws.receive_json()["message"]["sequence"] == 2
    with client.websocket_connect(path + "/ws?after=1") as ws:
        ws.send_json({"token": token})
        assert ws.receive_json()["message"]["sequence"] == 2
        client.post(path + "/close", headers=headers[1], json={"reason": "GENERAL"})
        assert ws.receive_json() == {"type": "room_closed", "reason": "GENERAL"}


@pytest.mark.parametrize("token_kind", ["other", "invalid", "refresh", "expired"])
def test_websocket_rejects_unauthorized_tokens(chat, token_kind):
    client, _, users, _, _, room = chat
    tokens = {
        "other": create_access_token(users[2]), "invalid": "bad",
        "refresh": create_refresh_token(users[1], uuid4()),
        "expired": _create_token(users[1], "access", timedelta(seconds=-1)),
    }
    with client.websocket_connect(f"/api/v1/chat/rooms/{room}/ws") as ws:
        ws.send_json({"token": tokens[token_kind]})
        assert ws.receive_json()["type"] == "error"
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_cors_supports_authenticated_chat_mutations(api_client):
    client, _ = api_client
    response = client.options("/api/v1/chat/rooms", headers={
        "Origin": "http://localhost:8081", "Access-Control-Request-Method": "PATCH",
        "Access-Control-Request-Headers": "Authorization,Content-Type",
    })
    assert response.status_code == 200
    assert "PATCH" in response.headers["access-control-allow-methods"]


def test_text_retry_is_idempotent_but_new_sends_remain_distinct(chat):
    client, _, _, headers, _, room = chat
    path = f"/api/v1/chat/rooms/{room}"
    body = {"content": "재전송 확인", "client_message_id": "text-attempt-1"}
    first = client.post(path + "/messages", headers=headers[1], json=body)
    retry = client.post(path + "/messages", headers=headers[1], json=body)
    assert first.status_code == retry.status_code == 201
    assert first.json() == retry.json()
    assert client.get(path, headers=headers[0]).json()["unread_count"] == 1
    assert client.post(path + "/messages", headers=headers[1], json={**body, "content": "다른 내용"}).status_code == 409
    intentional = client.post(path + "/messages", headers=headers[1], json={**body, "client_message_id": "text-attempt-2"})
    assert intentional.json()["id"] != first.json()["id"]
    other_sender = client.post(path + "/messages", headers=headers[0], json=body)
    assert other_sender.status_code == 201
    assert len(client.get(path + "/messages", headers=headers[0]).json()["items"]) == 3
    client.post(path + "/close", headers=headers[0], json={"reason": "GENERAL"})
    assert client.post(path + "/messages", headers=headers[1], json=body).json() == first.json()


def test_websocket_text_retry_shares_idempotency_with_http(chat):
    client, _, users, headers, _, room = chat
    path = f"/api/v1/chat/rooms/{room}"
    body = {"content": "한 번만 저장", "client_message_id": "cross-transport"}
    with client.websocket_connect(path + "/ws") as socket:
        socket.send_json({"token": create_access_token(users[1])})
        socket.send_json(body)
        first = socket.receive_json()["message"]
        assert client.post(path + "/messages", headers=headers[1], json=body).json()["id"] == first["id"]
        socket.send_json(body)
        socket.send_json({"content": "다음 메시지", "client_message_id": "next-message"})
        second = socket.receive_json()["message"]
        assert second["sequence"] == 2 and second["content"] == "다음 메시지"
    assert len(client.get(path + "/messages", headers=headers[0]).json()["items"]) == 2
