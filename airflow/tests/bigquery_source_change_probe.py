"""Verify real BigQuery sync after changes in a disposable PostgreSQL source."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import uuid4

import psycopg
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from pipeline import sync


def main() -> None:
    project = os.environ["GCP_PROJECT_ID"]
    dataset = os.environ["BIGQUERY_DATASET"]
    location = os.environ["BIGQUERY_LOCATION"]
    database_url = os.environ["SOURCE_DATABASE_URL"]
    parsed = urlparse(database_url)
    if ("_test_" not in dataset or
            parsed.hostname != "skku-analytics-probe-postgres" or
            parsed.path != "/probe" or
            os.environ.get("RUN_DISPOSABLE_SOURCE_PROBE") != "1"):
        raise ValueError("Probe requires the disposable PostgreSQL host and _test_ BigQuery dataset")

    name = f"posts_source_probe_{uuid4().hex[:12]}"
    target = f"{project}.{dataset}.{name}"
    client = bigquery.Client(project=project)
    try:
        client.get_table(target)
    except NotFound:
        pass
    else:
        raise RuntimeError(f"Probe target already exists: {target}")

    lost_id, found_id = uuid4(), uuid4()
    stamp = datetime.now(timezone.utc) + timedelta(minutes=10)
    original_time = stamp - timedelta(days=2)
    print(f"probe_table={target}", flush=True)
    sync.TABLES[name] = sync.TABLES["posts"]
    try:
        with psycopg.connect(database_url) as connection:
            connection.execute(
                "CREATE TABLE posts ("
                "id UUID PRIMARY KEY, post_type TEXT, category_id INTEGER, "
                "status TEXT, creation_method TEXT, event_start_at TIMESTAMPTZ, "
                "event_end_at TIMESTAMPTZ, created_at TIMESTAMPTZ, "
                "updated_at TIMESTAMPTZ, deleted_at TIMESTAMPTZ)"
            )
            connection.execute(
                "INSERT INTO posts (id, post_type, status, creation_method, created_at, updated_at) "
                "VALUES (%s, 'LOST', 'OPEN', 'MANUAL', %s, %s), "
                "(%s, 'FOUND', 'OPEN', 'MANUAL', %s, %s)",
                (lost_id, original_time, original_time,
                 found_id, original_time, original_time),
            )

        first = sync.sync_table(name, stamp, stamp, full_refresh=True)
        if first["source"] != 2 or first["target"] != 2:
            raise AssertionError(f"Initial load mismatch: {first}")
        print("initial_load=ok rows=2", flush=True)

        with psycopg.connect(database_url) as connection:
            connection.execute(
                "UPDATE posts SET status='COMPLETED', deleted_at=%s, updated_at=%s "
                "WHERE id=%s",
                (datetime.now(timezone.utc), datetime.now(timezone.utc), lost_id),
            )
        updated = sync.sync_table(name, stamp, stamp)
        result = list(client.query(
            f"SELECT status, deleted_at FROM `{target}` WHERE id = @id",
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("id", "STRING", str(lost_id))
            ]),
            location=location,
        ).result())
        if (updated["target"] != 2 or len(result) != 1 or
                result[0].status != "COMPLETED" or result[0].deleted_at is None):
            raise AssertionError(f"Soft delete did not propagate: {updated}, {result}")
        print("update_and_soft_delete=ok rows=2", flush=True)

        with psycopg.connect(database_url) as connection:
            connection.execute("DELETE FROM posts WHERE id=%s", (found_id,))
        deleted = sync.sync_table(name, stamp, stamp)
        if deleted["source"] != 1 or deleted["target"] != 1:
            raise AssertionError(f"Hard delete did not propagate: {deleted}")
        replay = sync.sync_table(name, stamp, stamp)
        if replay["source"] != 1 or replay["target"] != 1:
            raise AssertionError(f"Same-window replay changed result: {replay}")
        print("hard_delete_and_replay=ok rows=1", flush=True)
    finally:
        sync.TABLES.pop(name, None)
        client.delete_table(target, not_found_ok=True)
        print(f"probe_table_removed={target}", flush=True)


if __name__ == "__main__":
    main()
