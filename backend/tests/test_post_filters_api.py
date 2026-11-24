"""Real HTTP filter composition, ownership, snapshots and query validation."""

from uuid import UUID

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from test_posts_api import api_client, create_author
from app.core.security import create_access_token
from app.users.model import KeywordCondition, User
from app.posts.model import Category

ROOT = "/api/v1/posts"
SAVED = "/api/v1/users/me/keyword-conditions"


@pytest.fixture()
def filter_posts(api_client):
    client, engine = api_client
    owner = create_author(engine)
    headers = {"Authorization": f"Bearer {create_access_token(owner)}"}
    with Session(engine) as db:
        db.add_all([Category(id=1, code="ELECTRONICS", name="전자기기"), Category(id=2, code="BAG", name="가방")])
        db.commit()
    fixtures = [
        dict(title="혹시 에어팟 프로", description="검정 케이스", item_name="에어팟", category_id=1,
             locations=[{"location_text": "정문"}, {"location_text": "디도 뒷문"}],
             event_start_at="2026-11-24T09:00:00Z", event_end_at="2026-11-24T12:00:00Z"),
        dict(title="저기 이어폰", description="흰색 케이스", item_name="AirPods", category_id=1,
             locations=[{"location_text": "학생회관"}],
             event_start_at="2026-11-24T10:00:00Z", event_end_at="2026-11-24T11:00:00Z"),
        dict(title="검정 에어팟", description="새것", category_id=2, locations=[{"location_text": "디도"}]),
        dict(title="에어팟 검정", description="혹시 검정", category_id=1),
    ]
    ids = []
    for fixture in fixtures:
        created = client.post(ROOT, headers=headers, json={"post_type": "FOUND", **fixture})
        assert created.status_code == 201, created.text
        ids.append(created.json()["id"])
    source = client.post(ROOT, headers=headers, json={"post_type": "LOST", "title": "내 에어팟", "description": "비교 기준"}).json()["id"]
    return client, engine, owner, headers, ids, source


def found(client, params):
    response = client.get(ROOT, params=[("post_type", "FOUND"), *params])
    assert response.status_code == 200, response.text
    return response.json()


def test_phrase_is_contiguous_and_can_match_any_text_field(filter_posts):
    client, _, _, _, ids, _ = filter_posts
    assert {row["id"] for row in found(client, [("q", "에어팟 검정")])["items"]} == {ids[3]}
    assert {row["id"] for row in found(client, [("q", "검정 에어팟")])["items"]} == {ids[2]}
    assert found(client, [("q", "에어팟  검정")])["total"] == 0
    assert {row["id"] for row in found(client, [("q", "airpods")])["items"]} == {ids[1]}
    assert found(client, [("q", "케이스 에어팟")])["total"] == 0


def test_or_within_and_between_types_and_ranking_share_identical_predicates(filter_posts):
    client, engine, _, headers, ids, source = filter_posts
    terms = [("title_terms", "혹시"), ("title_terms", "저기")]
    assert {row["id"] for row in found(client, terms)["items"]} == set(ids[:2])
    terms += [("content_terms", "검정"), ("content_terms", "연두"), ("category_id", "1"),
              ("location_terms", "디도"), ("event_at", "2026-11-24T10:30:00Z")]
    page = found(client, terms)
    assert [row["id"] for row in page["items"]] == [ids[0]]
    ranked = client.get(f"{ROOT}/{source}/ranked-candidates", headers=headers, params=terms)
    assert ranked.status_code == 200, ranked.text
    assert [row["post"]["id"] for row in ranked.json()["items"]] == [ids[0]]
    assert ranked.json()["total"] == page["total"]
    other_run = client.get(f"{ROOT}/{source}/ranked-candidates", headers=headers,
                          params=[*terms, ("q", "絶対に一致しない")]).json()
    assert other_run["total"] == 0
    assert other_run["run_id"] != ranked.json()["run_id"]


def test_secondary_locations_match_without_duplicate_rows_or_alias_expansion(filter_posts):
    client, _, _, _, ids, _ = filter_posts
    page = found(client, [("location_terms", "디도"), ("location_terms", "뒷문"), ("limit", "1")])
    assert page["total"] == 2
    assert len(page["items"]) == 1
    assert found(client, [("location_terms", "삼성학술정보관")])["total"] == 0
    both = found(client, [("location_terms", "디도"), ("location_terms", "학생회관")])
    assert {row["id"] for row in both["items"]} == set(ids[:3])


@pytest.mark.parametrize("point,expected", [
    ("2026-11-24T09:00:00Z", 1), ("2026-11-24T10:30:00Z", 2),
    ("2026-11-24T12:00:00Z", 1), ("2026-11-24T12:00:01Z", 0),
    ("2026-11-24T19:30:00+09:00", 2),
])
def test_time_point_is_inclusive_and_unknown_times_are_excluded(filter_posts, point, expected):
    client, *_ = filter_posts
    assert found(client, [("event_at", point)])["total"] == expected


@pytest.mark.parametrize("params", [
    [("q", "   ")], [("q", "x" * 101)], [("title_terms", " ")],
    [("title_terms", "x")] * 21, [("category_id", "0")],
    [("event_at", "2026-11-24T12:00:00")], [("event_at", "invalid")],
])
def test_invalid_filters_return_422_in_both_routes(filter_posts, params):
    client, _, _, headers, _, source = filter_posts
    assert client.get(ROOT, params=params).status_code == 422
    assert client.get(f"{ROOT}/{source}/ranked-candidates", headers=headers, params=params).status_code == 422


def test_sql_wildcards_are_literal_and_blank_option_sets_do_not_filter(filter_posts):
    client, _, _, headers, ids, _ = filter_posts
    assert found(client, [("title_terms", "%")])["total"] == 0
    assert found(client, [("content_terms", "_")])["total"] == 0
    assert found(client, [])["total"] == 4
    created = client.post(ROOT, headers=headers, json={"post_type": "FOUND", "title": "100%_진짜", "description": "test"})
    assert created.status_code == 201
    assert found(client, [("q", "%_")])["total"] == 1


def test_saved_snapshot_reapplies_same_filters_and_is_private_and_persistent(filter_posts):
    client, engine, owner, headers, ids, _ = filter_posts
    payload = {"post_type": "FOUND", "conditions": {
        "q": "혹시 에어팟", "category_id": 1, "title_terms": ["혹시", "혹시", "저기"],
        "content_terms": ["검정"], "location_terms": ["디도", "학생회관"],
        "event_at": "2026-11-24T19:30:00+09:00",
    }}
    created = client.post(SAVED, headers=headers, json=payload)
    assert created.status_code == 201, created.text
    snapshot = created.json()
    assert snapshot["version"] == 1
    assert snapshot["conditions"]["title_terms"] == ["혹시", "저기"]
    page = client.get(SAVED, headers=headers).json()
    assert page["items"] == [snapshot] and page["total"] == 1
    with Session(engine) as db:
        row = db.get(KeywordCondition, UUID(snapshot["id"]))
        assert row.user_id == owner
        assert row.conditions["location_terms"] == ["디도", "학생회관"]
    payload["conditions"]["location_terms"].clear()
    assert client.get(SAVED, headers=headers).json()["items"] == [snapshot]
    params = []
    for field, value in snapshot["conditions"].items():
        if isinstance(value, list):
            params.extend((field, term) for term in value)
        elif value is not None:
            params.append((field, str(value)))
    assert [row["id"] for row in found(client, params)["items"]] == [ids[0]]
    other = create_author(engine, "private-keywords@skku.edu")
    other_headers = {"Authorization": f"Bearer {create_access_token(other)}"}
    assert client.get(SAVED, headers=other_headers).json()["items"] == []
    assert client.get(SAVED).status_code == 401
    assert client.post(SAVED, json=payload).status_code == 401


@pytest.mark.parametrize("payload", [
    {"post_type": "FOUND", "conditions": {}},
    {"post_type": "FOUND", "conditions": {"q": " "}},
    {"post_type": "OTHER", "conditions": {"q": "에어팟"}},
    {"post_type": "FOUND", "conditions": {"q": "에어팟", "unknown": "value"}},
    {"post_type": "FOUND", "conditions": {"category_id": 999}},
    {"post_type": "FOUND", "conditions": {"q": "에어팟"}, "user_id": "forged"},
])
def test_invalid_or_empty_saved_conditions_are_rejected(filter_posts, payload):
    client, _, _, headers, *_ = filter_posts
    assert client.post(SAVED, headers=headers, json=payload).status_code == 422
    assert client.get(SAVED, headers=headers).json()["total"] == 0


def test_saved_conditions_pagination_and_hard_user_delete_cascade(api_client):
    client, engine = api_client
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    owner = create_author(engine)
    headers = {"Authorization": f"Bearer {create_access_token(owner)}"}
    for q in ("first", "second", "third"):
        assert client.post(SAVED, headers=headers, json={"post_type": "FOUND", "conditions": {"q": q}}).status_code == 201
    page = client.get(SAVED, headers=headers, params={"limit": 1, "offset": 1}).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert page["items"][0]["conditions"]["q"] == "second"
    with Session(engine) as db:
        db.execute(delete(User).where(User.id == owner))
        db.commit()
        assert db.scalars(select(KeywordCondition)).all() == []
