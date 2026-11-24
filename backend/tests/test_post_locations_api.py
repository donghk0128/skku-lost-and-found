"""Ordered multi-location persistence, validation and legacy compatibility."""

from uuid import UUID

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from test_posts_api import api_client, create_author, post_payload
from app.core.security import create_access_token
from app.posts.model import Post, PostLocation
from app.posts.constants import MAX_POST_LOCATIONS


LOCATIONS = [
    {"location_text": "학생회관", "latitude": 37.588, "longitude": 126.993},
    {"location_text": "도서관", "latitude": 37.589, "longitude": 126.994},
    {"location_text": "버스 정류장"},
]


def authorized(engine):
    return {"Authorization": f"Bearer {create_access_token(create_author(engine))}"}


@pytest.mark.parametrize("endpoint", ["/api/v1/posts", "/api/v1/posts/ai-assisted"])
def test_locations_roundtrip_in_create_detail_and_list(api_client, endpoint):
    client, engine = api_client
    created = client.post(endpoint, headers=authorized(engine), json={**post_payload(), "locations": LOCATIONS})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["creation_method"] == ("AI_ASSISTED" if endpoint.endswith("ai-assisted") else "MANUAL")
    assert [row["location_text"] for row in body["locations"]] == [row["location_text"] for row in LOCATIONS]
    assert [row["position"] for row in body["locations"]] == [0, 1, 2]
    assert body["locations"][2]["latitude"] is None
    assert (body["location_text"], body["latitude"], body["longitude"]) == ("학생회관", 37.588, 126.993)
    assert client.get(f"/api/v1/posts/{body['id']}").json() == body
    assert client.get("/api/v1/posts").json()["items"] == [body]
    with Session(engine) as db:
        rows = db.scalars(select(PostLocation).where(PostLocation.post_id == UUID(body["id"]))
                          .order_by(PostLocation.position)).all()
        assert len(rows) == 3
        assert float(rows[1].longitude) == 126.994


def test_replace_reorder_shrink_clear_and_unrelated_update(api_client):
    client, engine = api_client
    headers = authorized(engine)
    body = client.post("/api/v1/posts", headers=headers, json={**post_payload(), "locations": LOCATIONS}).json()
    path = f"/api/v1/posts/{body['id']}"
    unchanged = client.patch(path, headers=headers, json={"title": "변경한 제목"})
    assert unchanged.status_code == 200
    assert unchanged.json()["locations"] == body["locations"]
    secondary = client.patch(path, headers=headers, json={"locations": [LOCATIONS[0], LOCATIONS[2]]})
    assert secondary.status_code == 200
    assert secondary.json()["latitude"] == body["latitude"]
    assert secondary.json()["updated_at"] != unchanged.json()["updated_at"]
    replaced = client.patch(path, headers=headers, json={"locations": [LOCATIONS[1], LOCATIONS[0]]})
    assert replaced.status_code == 200, replaced.text
    assert [row["position"] for row in replaced.json()["locations"]] == [0, 1]
    assert replaced.json()["latitude"] == LOCATIONS[1]["latitude"]
    cleared = client.patch(path, headers=headers, json={"locations": []})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["locations"] == []
    assert all(cleared.json()[key] is None for key in ("location_text", "latitude", "longitude"))
    with Session(engine) as db:
        assert db.scalars(select(PostLocation)).all() == []
    # Re-adding after a clear must not collide with previously deleted positions.
    added = client.patch(path, headers=headers, json={"locations": [{"latitude": 0, "longitude": 0}]})
    assert added.status_code == 200
    assert added.json()["latitude"] == 0


def test_empty_and_maximum_locations(api_client):
    client, engine = api_client
    headers = authorized(engine)
    assert client.get("/api/v1/posts/limits").json() == {"max_locations": MAX_POST_LOCATIONS}
    for locations in ([], [{"location_text": f"장소 {index}"} for index in range(MAX_POST_LOCATIONS)]):
        created = client.post("/api/v1/posts", headers=headers, json={**post_payload(), "locations": locations})
        assert created.status_code == 201, created.text
        assert len(created.json()["locations"]) == len(locations)
        assert created.json()["latitude"] is None
        saved_id = UUID(created.json()["id"])
        with Session(engine) as db:
            assert len(db.scalars(select(PostLocation).where(PostLocation.post_id == saved_id)).all()) == len(locations)


def test_text_only_primary_and_duplicate_coordinates_are_not_lost(api_client):
    client, engine = api_client
    headers = authorized(engine)
    locations = [LOCATIONS[2], LOCATIONS[0], LOCATIONS[0]]
    created = client.post("/api/v1/posts", headers=headers, json={**post_payload(), "locations": locations})
    assert created.status_code == 201
    body = created.json()
    assert body["latitude"] is None
    assert len(body["locations"]) == 3
    assert body["locations"][1]["latitude"] == LOCATIONS[0]["latitude"]
    assert body["locations"][2]["longitude"] == LOCATIONS[0]["longitude"]
    assert client.get(f"/api/v1/posts/{body['id']}").json()["locations"] == body["locations"]


@pytest.mark.parametrize("invalid", [
    None, [{}], [{"location_text": "   "}], [{"latitude": 37.5}], [{"longitude": 127}],
    [{"latitude": 91, "longitude": 127}], [{"latitude": 37, "longitude": -181}],
    [{"latitude": 37.1234567, "longitude": 127}], [{"location_text": "a" * 256}],
    [{"location_text": "도서관", "position": 1}], [{"location_text": "도서관"}] * (MAX_POST_LOCATIONS + 1),
])
def test_reject_invalid_locations_on_create_and_patch_without_data_loss(api_client, invalid):
    client, engine = api_client
    headers = authorized(engine)
    body = client.post("/api/v1/posts", headers=headers, json={**post_payload(), "locations": LOCATIONS}).json()
    path = f"/api/v1/posts/{body['id']}"
    for endpoint in ("/api/v1/posts", "/api/v1/posts/ai-assisted"):
        assert client.post(endpoint, headers=headers, json={**post_payload(), "locations": invalid}).status_code == 422
    assert client.patch(path, headers=headers, json={"locations": invalid}).status_code == 422
    assert client.get(path).json() == body


def test_legacy_create_and_patch_preserve_other_locations(api_client):
    client, engine = api_client
    headers = authorized(engine)
    created = client.post("/api/v1/posts", headers=headers, json={**post_payload(), **LOCATIONS[0]})
    assert created.status_code == 201
    assert created.json()["locations"] == [{"position": 0, **LOCATIONS[0]}]
    path = f"/api/v1/posts/{created.json()['id']}"
    client.patch(path, headers=headers, json={"locations": LOCATIONS})
    changed = client.patch(path, headers=headers, json={"location_text": "새 대표 장소"})
    assert changed.status_code == 200
    assert changed.json()["locations"][0]["location_text"] == "새 대표 장소"
    assert changed.json()["locations"][1:] == [
        {"position": index, "latitude": None, "longitude": None, **location}
        for index, location in enumerate(LOCATIONS[1:], start=1)
    ]
    # Clearing the representative via an old client promotes the next location.
    promoted = client.patch(path, headers=headers, json={"location_text": None, "latitude": None, "longitude": None})
    assert promoted.status_code == 200
    assert promoted.json()["location_text"] == "도서관"
    assert [row["position"] for row in promoted.json()["locations"]] == [0, 1]


def test_mixed_contract_and_unauthorized_writes_are_rejected(api_client):
    client, engine = api_client
    headers = authorized(engine)
    payload = {**post_payload(), "locations": LOCATIONS}
    assert client.post("/api/v1/posts", json=payload).status_code == 401
    created = client.post("/api/v1/posts", headers=headers, json=payload).json()
    path = f"/api/v1/posts/{created['id']}"
    other_id = create_author(engine, "other-locations@skku.edu")
    other_headers = {"Authorization": f"Bearer {create_access_token(other_id)}"}
    assert client.patch(path, headers=other_headers, json={"locations": []}).status_code == 403
    for legacy in ({"location_text": "장소"}, {"latitude": None, "longitude": None}):
        mixed = {"locations": [], **legacy}
        assert client.post("/api/v1/posts", headers=headers, json={**post_payload(), **mixed}).status_code == 422
        assert client.patch(path, headers=headers, json=mixed).status_code == 422
    assert client.get(path).json() == created


def test_hard_post_deletion_cascades_locations(api_client):
    client, engine = api_client
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    created = client.post("/api/v1/posts", headers=authorized(engine), json={**post_payload(), "locations": LOCATIONS}).json()
    with Session(engine) as db:
        # Account withdrawal uses a bulk post DELETE, which must also delete locations.
        db.execute(delete(Post).where(Post.id == UUID(created["id"])))
        db.commit()
        assert db.scalars(select(PostLocation)).all() == []
