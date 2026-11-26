"""Chat push outbox behavior without Firebase network access."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from test_posts_api import api_client  # noqa: F401 - fixture registration
from test_notifications import context, device, post, save  # noqa: F401 - fixture registration
from app.chat.model import ChatRoomMember
from app.notifications.model import ChatPushDelivery, ChatPushNotification, PushDelivery
from app.notifications.service import deliver_next
from app.users.model import now_utc

ROOMS = "/api/v1/chat/rooms"


class Sender:
    def __init__(self):
        self.sent = []

    def send(self, fid, notification):
        self.sent.append((fid, notification.room_id, notification.sequence, notification.body))


def start_chat(client, owner, requester):
    created = post(client, owner)
    response = client.post(ROOMS, headers=requester[1], json={"post_id": created["id"]})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def send(client, room, account, content, attempt):
    response = client.post(f"{ROOMS}/{room}/messages", headers=account[1], json={
        "content": content, "client_message_id": attempt,
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_chat_push_targets_other_participant_and_deduplicates_retry(context):
    client, engine, owner, requester = context
    device(client, owner)
    room = start_chat(client, owner, requester)
    send(client, room, requester, "첫 메시지", "attempt-1")
    send(client, room, requester, "첫 메시지", "attempt-1")
    sender = Sender()
    with Session(engine) as db:
        assert len(list(db.scalars(select(ChatPushNotification)))) == 1
        assert deliver_next(db, sender)
        assert not deliver_next(db, sender)
    assert len(sender.sent) == 1
    assert str(sender.sent[0][1]) == room
    assert sender.sent[0][3] == "첫 메시지"


def test_only_latest_unread_chat_message_is_delivered(context):
    client, engine, owner, requester = context
    device(client, owner)
    room = start_chat(client, owner, requester)
    send(client, room, requester, "이전", "attempt-1")
    send(client, room, requester, "최신", "attempt-2")
    sender = Sender()
    with Session(engine) as db:
        assert deliver_next(db, sender)
        assert deliver_next(db, sender)
        assert not deliver_next(db, sender)
        assert sorted(row.status for row in db.scalars(select(ChatPushDelivery))) == ["CANCELLED", "SENT"]
    assert [(row[2], row[3]) for row in sender.sent] == [(2, "최신")]


def test_read_and_logout_cancel_queued_chat_push(context):
    client, engine, owner, requester = context
    device(client, owner)
    room = start_chat(client, owner, requester)
    first = send(client, room, requester, "읽음", "attempt-1")
    read = client.patch(f"{ROOMS}/{room}/read", headers=owner[1], json={"sequence": first["sequence"]})
    assert read.status_code == 200
    sender = Sender()
    with Session(engine) as db:
        assert deliver_next(db, sender)
    send(client, room, requester, "로그아웃", "attempt-2")
    logout = client.post("/api/v1/auth/logout", json={"refresh_token": owner[2]})
    assert logout.status_code == 200
    with Session(engine) as db:
        assert deliver_next(db, sender)
        assert all(row.status == "CANCELLED" for row in db.scalars(select(ChatPushDelivery)))
        assert db.get(ChatRoomMember, (UUID(room), owner[0])).last_read_sequence == 1
    assert sender.sent == []


def test_chat_transport_uses_room_slot_and_navigation_data(context, monkeypatch):
    from firebase_admin import messaging
    from app.notifications.sender import FirebaseSender

    client, engine, owner, requester = context
    _, fid = device(client, owner)
    room = start_chat(client, owner, requester)
    send(client, room, requester, "미리보기", "attempt-1")
    captured = []
    monkeypatch.setattr(messaging, "send", lambda message, **_: captured.append(message))
    transport = FirebaseSender.__new__(FirebaseSender)
    transport.app = None
    with Session(engine) as db:
        assert deliver_next(db, transport)
    payload = captured[0]
    assert payload.fid == fid
    assert payload.data["type"] == "chat_message"
    assert payload.data["room_id"] == room
    assert payload.data["user_id"] == str(owner[0])
    assert payload.data["sequence"] == "1"
    assert payload.data["title"] and payload.data["body"] == "미리보기"
    assert payload.notification is None
    assert payload.android.notification is None
    assert payload.android.collapse_key is None
    assert payload.android.priority == "high"
    assert payload.apns.payload.aps.alert.body == "미리보기"
    assert payload.apns.headers["apns-collapse-id"] == f"chat-{room}"


def test_worker_can_alternate_keyword_and_chat_even_with_keyword_backlog(context):
    client, engine, owner, requester = context
    device(client, owner)
    save(client, owner)
    post(client, requester)
    room = start_chat(client, owner, requester)
    send(client, room, requester, "채팅", "attempt-1")
    with Session(engine) as db:
        keyword = db.scalar(select(PushDelivery))
        chat = db.scalar(select(ChatPushDelivery))
        keyword.next_attempt_at = now_utc() - timedelta(seconds=2)
        chat.next_attempt_at = now_utc() - timedelta(seconds=1)
        db.commit()

    class MixedSender:
        def __init__(self):
            self.kinds = []

        def send(self, _fid, notification):
            self.kinds.append("chat" if hasattr(notification, "room_id") else "keyword")

    sender = MixedSender()
    with Session(engine) as db:
        assert deliver_next(db, sender, prefer_chat=True)
        assert deliver_next(db, sender, prefer_chat=False)
    assert sender.kinds == ["chat", "keyword"]
