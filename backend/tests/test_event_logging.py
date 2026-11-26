"""Event idempotency, privacy contract, and confirmed return labels."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from test_posts_api import api_client, create_author  # noqa: F401
from app.core.security import create_access_token
from app.chat.model import ReturnPair
from app.events.model import EventLog
from app.users.model import User
from app.users.withdrawal import WithdrawalService


def headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def test_event_retry_keeps_one_row_and_rejects_free_text(api_client):
    client, engine = api_client
    user_id = create_author(engine, "events@skku.edu")
    event_id = uuid4()
    body = {
        "event_id": str(event_id), "event_type": "screen_view", "screen": "home",
        "visit_id": str(uuid4()), "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    assert client.post("/api/v1/events", json=body).status_code == 401
    first = client.post("/api/v1/events", headers=headers(user_id), json=body)
    assert first.status_code == 202 and first.json()["accepted"] is True
    repeat = client.post("/api/v1/events", headers=headers(user_id), json=body)
    assert repeat.status_code == 202 and repeat.json()["accepted"] is False
    assert client.post("/api/v1/events", headers=headers(user_id), json={**body, "query": "010-1234-5678"}).status_code == 422
    with Session(engine) as db:
        row = db.get(EventLog, event_id)
        assert row.user_id == user_id and row.received_at is not None
        assert row.properties == {"screen": "home"}
        assert len(list(db.scalars(select(EventLog)))) == 1


def test_return_pair_requires_other_participant_confirmation(api_client):
    client, engine = api_client
    owner = create_author(engine, "pair-owner@skku.edu")
    requester = create_author(engine, "pair-requester@skku.edu")
    primary = client.post("/api/v1/posts", headers=headers(owner), json={
        "post_type": "LOST", "title": "분실한 지갑", "description": "검은색",
    }).json()["id"]
    counterpart = client.post("/api/v1/posts", headers=headers(requester), json={
        "post_type": "FOUND", "title": "습득한 지갑", "description": "검은색",
    }).json()["id"]
    room = client.post("/api/v1/chat/rooms", headers=headers(requester), json={"post_id": primary}).json()["id"]
    base = f"/api/v1/chat/rooms/{room}"
    candidates = client.get(base + "/pair-candidates", headers=headers(owner)).json()
    assert [row["id"] for row in candidates] == [counterpart]
    proposed = client.post(base + "/return-pair", headers=headers(owner), json={"counterpart_post_id": counterpart})
    assert proposed.status_code == 200 and proposed.json()["return_pair"]["status"] == "PENDING"
    assert proposed.json()["return_pair"]["counterpart_post_title"] == "습득한 지갑"
    assert client.get(f"/api/v1/posts/{primary}").json()["status"] == "OPEN"
    assert client.post(base + "/return-pair/confirm", headers=headers(owner), json={}).status_code == 403
    confirmed = client.post(base + "/return-pair/confirm", headers=headers(requester), json={})
    assert confirmed.status_code == 200 and confirmed.json()["return_pair"]["status"] == "CONFIRMED"
    assert confirmed.json()["close_reason"] == "RETURNED"
    for post_id in (primary, counterpart):
        assert client.get(f"/api/v1/posts/{post_id}").json()["status"] == "COMPLETED"
    with Session(engine) as db:
        pair = db.scalar(select(ReturnPair).where(ReturnPair.room_id == UUID(room)))
        assert pair.status == "CONFIRMED"
        assert (str(pair.lost_post_id), str(pair.found_post_id)) == (primary, counterpart)
        assert db.scalar(select(EventLog).where(EventLog.event_type == "match_confirmed")) is not None


def test_direct_completion_does_not_create_pair(api_client):
    client, engine = api_client
    owner = create_author(engine, "direct-owner@skku.edu")
    post = client.post("/api/v1/posts", headers=headers(owner), json={
        "post_type": "FOUND", "title": "습득물", "description": "지갑",
    }).json()["id"]
    result = client.patch(f"/api/v1/posts/{post}/status", headers=headers(owner), json={"status": "COMPLETED"})
    assert result.status_code == 200
    with Session(engine) as db:
        assert db.scalar(select(ReturnPair)) is None
        assert db.scalar(select(EventLog).where(EventLog.event_type == "post_completed")) is not None


def test_returned_post_is_not_later_labeled_direct_completion(api_client):
    client, engine = api_client
    owner = create_author(engine, "return-owner@skku.edu")
    requester = create_author(engine, "return-requester@skku.edu")
    post = client.post("/api/v1/posts", headers=headers(owner), json={
        "post_type": "FOUND", "title": "반환할 물건", "description": "설명",
    }).json()["id"]
    room = client.post("/api/v1/chat/rooms", headers=headers(requester), json={"post_id": post}).json()["id"]
    assert client.post(f"/api/v1/chat/rooms/{room}/close", headers=headers(owner),
                       json={"reason": "RETURNED"}).status_code == 200
    assert client.patch(f"/api/v1/posts/{post}/status", headers=headers(owner),
                        json={"status": "COMPLETED"}).status_code == 200
    with Session(engine) as db:
        assert db.scalar(select(EventLog).where(EventLog.event_type == "return_completed")) is not None
        assert db.scalar(select(EventLog).where(EventLog.event_type == "post_completed")) is None


def test_recommendation_event_checks_run_candidate_and_rank(api_client):
    client, engine = api_client
    owner = create_author(engine, "rank-owner@skku.edu")
    finder = create_author(engine, "rank-finder@skku.edu")
    source = client.post("/api/v1/posts", headers=headers(owner), json={
        "post_type": "LOST", "title": "분실한 가방", "description": "검정 가방",
    }).json()["id"]
    candidate = client.post("/api/v1/posts", headers=headers(finder), json={
        "post_type": "FOUND", "title": "습득한 가방", "description": "검정 가방",
    }).json()["id"]
    ranked = client.get(f"/api/v1/posts/{source}/ranked-candidates", headers=headers(owner))
    assert ranked.status_code == 200
    result = ranked.json()
    item = next(row for row in result["items"] if row["post"]["id"] == candidate)
    body = {
        "event_id": str(uuid4()), "event_type": "recommendation_impression",
        "visit_id": str(uuid4()), "occurred_at": datetime.now(timezone.utc).isoformat(),
        "run_id": result["run_id"], "source_post_id": source,
        "candidate_post_id": candidate, "rank": item["rank"],
    }
    assert client.post("/api/v1/events", headers=headers(owner), json=body).json()["accepted"] is True
    assert client.post("/api/v1/events", headers=headers(owner), json=body).json()["accepted"] is False
    assert client.post("/api/v1/events", headers=headers(owner), json={**body, "event_id": str(uuid4()), "rank": 999}).status_code == 422


def test_event_storage_failure_does_not_fail_post_creation(api_client):
    client, engine = api_client
    owner = create_author(engine, "logging-failure@skku.edu")
    EventLog.__table__.drop(engine)
    result = client.post("/api/v1/posts", headers=headers(owner), json={
        "post_type": "FOUND", "title": "로그 실패 테스트", "description": "게시글은 저장돼야 함",
    })
    assert result.status_code == 201
    assert client.get(f"/api/v1/posts/{result.json()['id']}").status_code == 200


def test_withdrawal_removes_user_events_and_pending_pair(api_client):
    client, engine = api_client
    owner = create_author(engine, "erase-owner@skku.edu")
    requester = create_author(engine, "erase-requester@skku.edu")
    primary = client.post("/api/v1/posts", headers=headers(owner), json={
        "post_type": "LOST", "title": "분실물", "description": "설명",
    }).json()["id"]
    counterpart = client.post("/api/v1/posts", headers=headers(requester), json={
        "post_type": "FOUND", "title": "습득물", "description": "설명",
    }).json()["id"]
    room = client.post("/api/v1/chat/rooms", headers=headers(requester), json={"post_id": primary}).json()["id"]
    assert client.post(f"/api/v1/chat/rooms/{room}/return-pair", headers=headers(owner),
                       json={"counterpart_post_id": counterpart}).status_code == 200
    with Session(engine) as db:
        assert db.scalar(select(ReturnPair)) is not None
        assert db.scalar(select(EventLog).where(EventLog.user_id == owner)) is not None
        WithdrawalService.remove_rows(db, db.get(User, owner))
        db.commit()
        assert db.scalar(select(ReturnPair)) is None
        assert db.scalar(select(EventLog).where(EventLog.user_id == owner)) is None
