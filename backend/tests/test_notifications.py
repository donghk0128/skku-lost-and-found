"""HTTP, outbox and worker tests; never send a real push or load a private key."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from test_posts_api import api_client, create_author
from app.auth.service import AuthService
from app.core.config import get_settings
from app.core.security import create_access_token
from app.notifications.model import PushDelivery, PushDevice, PushNotification
from app.notifications.sender import PushSendError
from app.notifications.service import deliver_next
from app.posts.model import Post
from app.users.model import KeywordCondition, now_utc

SAVED = "/api/v1/users/me/keyword-conditions"
DEVICES = "/api/v1/users/me/push-devices"
POSTS = "/api/v1/posts"


@pytest.fixture()
def context(api_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "push_enabled", True)
    client, engine = api_client
    def account(email):
        uid = create_author(engine, email)
        with Session(engine) as db:
            session, refresh = AuthService._create_session(uid)
            db.add(session)
            db.commit()
        return uid, {"Authorization": f"Bearer {create_access_token(uid)}"}, refresh
    owner = account("push-owner@skku.edu")
    author = account("push-author@skku.edu")
    return client, engine, owner, author


def save(client, account, conditions=None, enabled=True):
    row = client.post(SAVED, headers=account[1], json={"post_type": "FOUND", "conditions": conditions or {"q": "에어팟"}})
    assert row.status_code == 201, row.text
    row = row.json()
    assert row["notification_enabled"] is False
    if enabled:
        response = client.patch(f"{SAVED}/{row['id']}", headers=account[1], json={"notification_enabled": True})
        assert response.status_code == 200, response.text
    return row


def device(client, account, *, installation=None, fid=None, platform="android"):
    installation = installation or str(uuid4())
    fid = fid or uuid4().hex
    response = client.post(DEVICES, headers=account[1], json={
        "installation_id": installation, "platform": platform, "fid": fid, "refresh_token": account[2],
    })
    assert response.status_code == 204, response.text
    return installation, fid


def post(client, account, **overrides):
    response = client.post(POSTS, headers=account[1], json={
        "post_type": "FOUND", "title": "에어팟 발견", "description": "검정 케이스", **overrides,
    })
    assert response.status_code == 201, response.text
    return response.json()


class Sender:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def send(self, fid, notification):
        self.calls.append((fid, notification.post_id))
        if self.error:
            raise self.error


def test_conditions_are_owned_opt_in_and_deletable(context):
    client, engine, owner, other = context
    condition = save(client, owner, enabled=False)
    path = f"{SAVED}/{condition['id']}"
    for method in ("patch", "delete"):
        kwargs = {"json": {"notification_enabled": True}} if method == "patch" else {}
        assert getattr(client, method)(path, headers=other[1], **kwargs).status_code == 404
    assert client.patch(path, headers=owner[1], json={"notification_enabled": True}).status_code == 200
    with Session(engine) as db:
        row = db.get(KeywordCondition, UUID(condition["id"]))
        original_enabled_at, original_conditions = row.notification_enabled_at, row.conditions
    assert client.patch(path, headers=owner[1], json={"notification_enabled": True}).status_code == 200
    with Session(engine) as db:
        row = db.get(KeywordCondition, UUID(condition["id"]))
        assert row.notification_enabled_at == original_enabled_at
        assert row.conditions == original_conditions
    assert client.delete(path, headers=owner[1]).status_code == 204
    assert client.get(SAVED, headers=owner[1]).json()["total"] == 0


def test_device_requires_live_own_session_and_preserves_generation_on_heartbeat(context):
    client, engine, owner, other = context
    installation, fid = device(client, owner)
    with Session(engine) as db:
        generation = db.get(PushDevice, UUID(installation)).generation
    device(client, owner, installation=installation, fid=fid)
    with Session(engine) as db:
        assert db.get(PushDevice, UUID(installation)).generation == generation
    data = {"installation_id": installation, "fid": fid, "platform": "ios", "refresh_token": owner[2]}
    assert client.post(DEVICES, headers=other[1], json=data).status_code == 401
    assert client.delete(f"{DEVICES}/{installation}", headers=other[1]).status_code == 204
    with Session(engine) as db:
        assert db.get(PushDevice, UUID(installation)) is not None
    assert client.post("/api/v1/auth/logout", json={"refresh_token": owner[2]}).status_code == 200
    assert client.post(DEVICES, headers=owner[1], json=data).status_code == 401


def test_multiple_conditions_deduplicate_per_post_and_deliver_to_each_device(context):
    client, engine, owner, author = context
    save(client, owner)
    save(client, owner, {"content_terms": ["검정", "흰색"]})
    device(client, owner)
    device(client, owner, platform="ios")
    created = post(client, author)
    sender = Sender()
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(PushNotification)) == 1
        assert db.scalar(select(func.count()).select_from(PushDelivery)) == 2
        assert deliver_next(db, sender)
        assert deliver_next(db, sender)
        assert not deliver_next(db, sender)
        assert all(row.status == "SENT" for row in db.scalars(select(PushDelivery)))
    assert len(sender.calls) == 2
    assert all(str(post_id) == created["id"] for _, post_id in sender.calls)


@pytest.mark.parametrize("changes,expected", [
    ({"title": "혹시 에어팟", "locations": [{"location_text": "정문"}, {"location_text": "디도 뒷문"}]}, 1),
    ({"title": "저기 에어팟", "locations": [{"location_text": "학생회관"}]}, 1),
    ({"title": "저기 에어팟", "locations": [{"location_text": "정문"}]}, 0),
    ({"title": "에어팟", "locations": [{"location_text": "디도"}]}, 0),
    ({"title": "혹시 에어팟", "description": "파랑", "locations": [{"location_text": "디도"}]}, 0),
    ({"title": "혹시 에어팟", "post_type": "LOST", "locations": [{"location_text": "디도"}]}, 0),
])
def test_filter_semantics_include_secondary_locations(context, changes, expected):
    client, engine, owner, author = context
    save(client, owner, {"q": "에어팟", "title_terms": ["혹시", "저기"],
        "content_terms": ["검정", "흰색"], "location_terms": ["디도", "학생회관"]})
    device(client, owner)
    post(client, author, **changes)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(PushNotification)) == expected


def test_no_backfill_no_own_posts_no_update_notifications(context):
    client, engine, owner, author = context
    device(client, owner)
    old = post(client, author)
    save(client, owner)
    post(client, owner)
    assert client.patch(f"{POSTS}/{old['id']}", headers=author[1], json={"title": "에어팟 수정"}).status_code == 200
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(PushNotification)) == 0
    post(client, author)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(PushNotification)) == 1


@pytest.mark.parametrize("action", ["disable", "delete", "logout", "switch", "unregister", "complete", "delete_post", "reenable"])
def test_pending_delivery_is_cancelled_when_no_longer_eligible(context, action):
    client, engine, owner, author = context
    condition = save(client, owner)
    installation, fid = device(client, owner)
    created = post(client, author)
    path = f"{SAVED}/{condition['id']}"
    if action in ("disable", "reenable"):
        client.patch(path, headers=owner[1], json={"notification_enabled": False})
        if action == "reenable":
            client.patch(path, headers=owner[1], json={"notification_enabled": True})
    elif action == "delete":
        client.delete(path, headers=owner[1])
    elif action == "logout":
        client.post("/api/v1/auth/logout", json={"refresh_token": owner[2]})
    elif action == "switch":
        device(client, author, installation=installation, fid=fid)
    elif action == "unregister":
        client.delete(f"{DEVICES}/{installation}", headers=owner[1])
    elif action == "complete":
        client.patch(f"{POSTS}/{created['id']}/status", headers=author[1], json={"status": "COMPLETED"})
    elif action == "delete_post":
        client.delete(f"{POSTS}/{created['id']}", headers=author[1])
    sender = Sender()
    with Session(engine) as db:
        deliver_next(db, sender)
        assert all(row.status == "CANCELLED" for row in db.scalars(select(PushDelivery)))
    assert sender.calls == []


def test_retry_is_durable_and_successful_delivery_is_not_repeated(context):
    client, engine, owner, author = context
    save(client, owner)
    device(client, owner)
    post(client, author)
    sender = Sender(PushSendError("unavailable"))
    with Session(engine) as db:
        assert deliver_next(db, sender)
        delivery = db.scalar(select(PushDelivery))
        assert delivery.status == "PENDING" and delivery.attempts == 1
        assert not deliver_next(db, sender)
        delivery.next_attempt_at = now_utc() - timedelta(seconds=1)
        db.commit()
        sender.error = None
        assert deliver_next(db, sender)
        assert not deliver_next(db, sender)
        db.refresh(delivery)
        assert delivery.status == "SENT" and delivery.attempts == 2


def test_invalid_registration_is_disabled(context):
    client, engine, owner, author = context
    save(client, owner)
    device(client, owner)
    post(client, author)
    with Session(engine) as db:
        assert deliver_next(db, Sender(PushSendError("unregistered", permanent=True, invalid_device=True)))
        assert db.scalar(select(PushDelivery)).status == "FAILED"
        assert db.scalar(select(PushDevice)).enabled is False


def test_retry_limit_and_expiry_stop_delivery(context, monkeypatch):
    client, engine, owner, author = context
    monkeypatch.setattr(get_settings(), "push_max_attempts", 1)
    save(client, owner)
    device(client, owner)
    post(client, author)
    with Session(engine) as db:
        assert deliver_next(db, Sender(PushSendError("unavailable")))
        assert db.scalar(select(PushDelivery)).status == "FAILED"
    post(client, author)
    sender = Sender()
    with Session(engine) as db:
        for notification in db.scalars(select(PushNotification)):
            notification.created_at = now_utc() - timedelta(days=2)
        db.commit()
        assert deliver_next(db, sender)
    assert not sender.calls


def test_disabling_one_of_multiple_matches_keeps_the_other(context):
    client, engine, owner, author = context
    first = save(client, owner)
    save(client, owner, {"content_terms": ["검정"]})
    device(client, owner)
    post(client, author)
    client.patch(f"{SAVED}/{first['id']}", headers=owner[1], json={"notification_enabled": False})
    sender = Sender()
    with Session(engine) as db:
        assert deliver_next(db, sender)
    assert len(sender.calls) == 1


def test_rollback_removes_post_and_outbox_together(context, monkeypatch):
    from app.posts.service import PostService
    from app.posts.schemas import PostCreateRequest
    from app.users.model import User
    client, engine, owner, author = context
    save(client, owner)
    device(client, owner)
    def fail(db):
        db.rollback()
        raise RuntimeError("simulate failed commit")
    monkeypatch.setattr(PostService, "_commit", fail)
    with Session(engine) as db:
        with pytest.raises(RuntimeError):
            PostService.create(db, PostCreateRequest(post_type="FOUND", title="에어팟", description="검정"), db.get(User, author[0]))
        assert db.scalar(select(func.count()).select_from(Post)) == 0
        assert db.scalar(select(func.count()).select_from(PushNotification)) == 0


def test_disabled_server_creates_no_historical_backlog(context, monkeypatch):
    client, engine, owner, author = context
    save(client, owner)
    device(client, owner)
    monkeypatch.setattr(get_settings(), "push_enabled", False)
    post(client, author)
    monkeypatch.setattr(get_settings(), "push_enabled", True)
    with Session(engine) as db:
        assert not deliver_next(db, Sender())


def test_transport_builds_cross_platform_payload_without_network(context, monkeypatch):
    from firebase_admin import messaging
    from app.notifications.sender import FirebaseSender
    client, engine, owner, author = context
    save(client, owner)
    _, fid = device(client, owner)
    post(client, author)
    captured = []
    monkeypatch.setattr(messaging, "send", lambda message, **_: captured.append(message))
    sender = FirebaseSender.__new__(FirebaseSender)
    sender.app = None
    with Session(engine) as db:
        assert deliver_next(db, sender)
    message = captured[0]
    assert message.fid == fid
    assert message.data["user_id"] == str(owner[0])
    assert message.android.notification.channel_id == "keyword-posts"
    assert message.android.notification.tag == message.data["notification_id"]
    assert message.apns.headers["apns-collapse-id"] == message.data["notification_id"]
