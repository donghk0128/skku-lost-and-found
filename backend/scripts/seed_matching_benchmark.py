"""Create the fixed matching benchmark in a development DB and write private labels.

Run from backend. Without --apply this validates the dataset without connecting to DB.
Never run against production data. The posts are visible OPEN posts in the target DB.
"""

import argparse
import csv
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5


DEFAULT_DATASET = Path("evaluation/benchmark_v1.json")
DEFAULT_LABELS = Path("evaluation/labels.csv")


def post_id(dataset_name: str, code: str, kind: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"skku-finder/{dataset_name}/{code}/{kind}")


def locations_for(data: dict, entry: dict) -> list[dict]:
    """Return ordered locations; the original benchmark has one legacy anchor."""
    if "locations" in entry:
        return entry["locations"]
    if entry.get("location_text") is None and entry.get("anchor") is None:
        return []
    return [{"location_text": entry.get("location_text"), "anchor": entry.get("anchor")}]


def location_values(data: dict, location: dict) -> tuple[str | None, Decimal | None, Decimal | None]:
    anchor = data["anchors"].get(location.get("anchor")) if location.get("anchor") else None
    return (
        location.get("location_text"),
        Decimal(str(anchor[0])) if anchor else None,
        Decimal(str(anchor[1])) if anchor else None,
    )


def load_dataset(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    pairs = data["pairs"]
    if len(pairs) < 6 or len({pair["code"] for pair in pairs}) != len(pairs):
        raise ValueError("Benchmark needs at least six uniquely coded positive pairs")
    for pair in pairs:
        if pair["category_code"] not in {"ELECTRONICS", "WALLET", "KEY", "OTHER"}:
            raise ValueError(f"Unexpected category in {pair['code']}")
        for kind in ("lost", "found"):
            entry = pair[kind]
            if not entry["title"].strip() or not entry["description"].strip():
                raise ValueError(f"Missing text in {pair['code']}/{kind}")
            locations = locations_for(data, entry)
            if not locations or len(locations) > 10:
                raise ValueError(f"Expected 1-10 locations in {pair['code']}/{kind}")
            for location in locations:
                anchor = location.get("anchor")
                if anchor is not None and anchor not in data["anchors"]:
                    raise ValueError(f"Unknown anchor in {pair['code']}/{kind}")
                if not location.get("location_text") and anchor is None:
                    raise ValueError(f"Empty location in {pair['code']}/{kind}")
            start = datetime.fromisoformat(entry["event_start_at"])
            end = datetime.fromisoformat(entry["event_end_at"])
            if start.tzinfo is None or end.tzinfo is None or start > end:
                raise ValueError(f"Invalid time range in {pair['code']}/{kind}")
    return data


def write_labels(data: dict, path: Path) -> None:
    pairs = data["pairs"]
    rows = []
    for source_kind, candidate_kind in (("lost", "found"), ("found", "lost")):
        for source in pairs:
            source_id = post_id(data["name"], source["code"], source_kind)
            for candidate in pairs:
                rows.append((
                    str(source_id),
                    str(post_id(data["name"], candidate["code"], candidate_kind)),
                    int(source["code"] == candidate["code"]),
                    source["code"],
                    candidate["code"],
                ))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("source_post_id", "candidate_post_id", "label", "source_code", "candidate_code"))
        writer.writerows(rows)


def seed(data: dict, lost_author_id: UUID, found_author_id: UUID) -> None:
    from sqlalchemy import inspect, select
    from sqlalchemy.orm import Session

    from app.core.config import get_settings
    from app.core.database import engine
    from app.matching.embedding import sync_post_embedding
    from app.matching.model import PostEmbedding
    from app.posts.model import Category, Post, PostLocation
    from app.users.model import User

    expected = {
        post_id(data["name"], pair["code"], kind)
        for pair in data["pairs"] for kind in ("lost", "found")
    }
    with Session(engine) as db:
        if db.get_bind().dialect.name != "postgresql":
            raise ValueError("Benchmark seeding requires the development PostgreSQL DB")
        if any("locations" in pair[kind] for pair in data["pairs"] for kind in ("lost", "found")):
            if not inspect(db.connection()).has_table("post_locations"):
                raise ValueError("post_locations is missing; apply the 0013_post_locations migration before seeding")
        for author_id in {lost_author_id, found_author_id}:
            if db.get(User, author_id) is None:
                raise ValueError(f"Test author does not exist: {author_id}")
        categories = {row.code: row.id for row in db.scalars(select(Category)).all()}
        for pair in data["pairs"]:
            if pair["category_code"] not in categories:
                raise ValueError(f"Missing category: {pair['category_code']}")
        existing_posts = list(db.scalars(select(Post).where(Post.id.in_(expected))).all())
        existing = {post.id for post in existing_posts}
        if existing:
            if existing != expected:
                raise ValueError("Partial benchmark exists; no changes made")
            for pair in data["pairs"]:
                for kind in ("lost", "found"):
                    post = next(post for post in existing_posts if post.id == post_id(data["name"], pair["code"], kind))
                    entry = pair[kind]
                    locations = locations_for(data, entry)
                    first = location_values(data, locations[0])
                    if (
                        post.author_id, post.post_type, post.title, post.description, post.item_name,
                        post.category_id, post.location_text, post.latitude, post.longitude,
                        post.event_start_at, post.event_end_at, post.status, post.creation_method,
                        post.deleted_at,
                    ) != (
                        lost_author_id if kind == "lost" else found_author_id,
                        kind.upper(), entry["title"], entry["description"], None,
                        categories[pair["category_code"]], *first,
                        datetime.fromisoformat(entry["event_start_at"]),
                        datetime.fromisoformat(entry["event_end_at"]),
                        "OPEN", "MANUAL", None,
                    ):
                        raise ValueError(f"Benchmark post changed: {pair['code']}/{kind}")
                    if "locations" in entry:
                        expected_locations = [location_values(data, location) for location in locations]
                        actual_locations = [
                            (location.location_text, location.latitude, location.longitude)
                            for location in post.locations
                        ]
                        if actual_locations != expected_locations:
                            raise ValueError(f"Benchmark locations changed: {pair['code']}/{kind}")
            if set(db.scalars(select(PostEmbedding.post_id).where(PostEmbedding.post_id.in_(expected))).all()) != expected:
                raise ValueError("Benchmark posts exist but some embeddings are missing")
            print(f"Reusing {len(expected)} existing benchmark posts; no DB changes")
            return
        if not get_settings().gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required to seed comparable embeddings")
        for pair in data["pairs"]:
            for kind, author_id in (("lost", lost_author_id), ("found", found_author_id)):
                entry = pair[kind]
                locations = locations_for(data, entry)
                first = location_values(data, locations[0])
                post = Post(
                    id=post_id(data["name"], pair["code"], kind),
                    author_id=author_id,
                    post_type=kind.upper(),
                    title=entry["title"],
                    description=entry["description"],
                    item_name=None,
                    category_id=categories[pair["category_code"]],
                    location_text=first[0],
                    latitude=first[1],
                    longitude=first[2],
                    event_start_at=datetime.fromisoformat(entry["event_start_at"]),
                    event_end_at=datetime.fromisoformat(entry["event_end_at"]),
                    status="OPEN",
                    creation_method="MANUAL",
                )
                if "locations" in entry:
                    post.locations = [
                        PostLocation(
                            position=position, location_text=values[0],
                            latitude=values[1], longitude=values[2],
                        )
                        for position, location in enumerate(locations)
                        for values in [location_values(data, location)]
                    ]
                db.add(post)
                db.flush()
                if not sync_post_embedding(db, post):
                    raise RuntimeError(f"Embedding failed for {pair['code']}/{kind}; transaction rolled back")
        db.commit()
        print(f"Created {len(expected)} benchmark posts with embeddings")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--lost-author-id", type=UUID)
    parser.add_argument("--found-author-id", type=UUID)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    data = load_dataset(args.dataset)
    count = len(data["pairs"])
    print(f"Validated {count} pairs, {2 * count} posts, {2 * count * count} labeled comparisons")
    if not args.apply:
        print("Dry run only. Pass --apply and a test author ID to write to the development DB.")
        return
    if args.lost_author_id is None:
        parser.error("--lost-author-id is required with --apply")
    seed(data, args.lost_author_id, args.found_author_id or args.lost_author_id)
    write_labels(data, args.labels)
    print(f"Wrote private labels to {args.labels}")


if __name__ == "__main__":
    main()
