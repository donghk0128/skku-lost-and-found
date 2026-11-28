"""Idempotent, bounded-column raw sync for the capstone analytics tables.

Incremental rows are merged by source key. A same-snapshot key scan removes
source rows hard-deleted on account withdrawal; soft-deleted posts remain with
their ``deleted_at`` value. No source free-text or image fields are queried.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from google.api_core.exceptions import NotFound
from google.cloud import bigquery
from psycopg.rows import dict_row


@dataclass(frozen=True)
class TableSpec:
    name: str
    columns: tuple[tuple[str, str], ...]
    keys: tuple[str, ...]
    change_time: str
    source: str


TABLES = {
    "event_logs": TableSpec(
        "event_logs",
        (("id", "STRING"), ("user_id", "STRING"), ("event_type", "STRING"),
         ("occurred_at", "TIMESTAMP"), ("received_at", "TIMESTAMP"),
         ("visit_id", "STRING"), ("post_id", "STRING"),
         ("source_post_id", "STRING"), ("candidate_post_id", "STRING"),
         ("run_id", "STRING"), ("rank", "INT64"), ("properties", "STRING")),
        ("id",), "received_at", "event_logs",
    ),
    "posts": TableSpec(
        "posts",
        (("id", "STRING"), ("post_type", "STRING"), ("category_id", "INT64"),
         ("status", "STRING"), ("creation_method", "STRING"),
         ("event_start_at", "TIMESTAMP"), ("event_end_at", "TIMESTAMP"),
         ("created_at", "TIMESTAMP"), ("updated_at", "TIMESTAMP"),
         ("deleted_at", "TIMESTAMP")),
        ("id",), "updated_at", "posts",
    ),
    "return_pairs": TableSpec(
        "return_pairs",
        (("id", "STRING"), ("room_id", "STRING"), ("lost_post_id", "STRING"),
         ("found_post_id", "STRING"), ("status", "STRING"),
         ("created_at", "TIMESTAMP"), ("confirmed_at", "TIMESTAMP")),
        ("id",), "COALESCE(confirmed_at, created_at)", "return_pairs",
    ),
    "recommendation_runs": TableSpec(
        "recommendation_runs",
        (("id", "STRING"), ("source_post_id", "STRING"),
         ("algorithm_version", "STRING"), ("candidate_count", "INT64"),
         ("generated_at", "TIMESTAMP")),
        ("id",), "generated_at", "recommendation_runs",
    ),
    "recommendation_items": TableSpec(
        "recommendation_items",
        (("run_id", "STRING"), ("candidate_post_id", "STRING"),
         ("rank", "INT64"), ("final_score", "FLOAT64"),
         ("rule_score", "FLOAT64"), ("semantic_score", "FLOAT64"),
         ("text_score", "FLOAT64"), ("category_score", "FLOAT64"),
         ("time_score", "FLOAT64"), ("location_score", "FLOAT64"),
         ("color_conflict", "BOOL"), ("distance_km", "FLOAT64"),
         ("time_gap_hours", "FLOAT64")),
        ("run_id", "candidate_post_id"), "r.generated_at",
        "recommendation_items AS i JOIN recommendation_runs AS r ON r.id = i.run_id",
    ),
}


def _config() -> tuple[str, str, str, str]:
    values = tuple(os.environ[name] for name in (
        "SOURCE_DATABASE_URL", "GCP_PROJECT_ID", "BIGQUERY_DATASET", "BIGQUERY_LOCATION"
    ))
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", values[1]):
        raise ValueError("Invalid GCP_PROJECT_ID")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,1023}", values[2]):
        raise ValueError("Invalid BIGQUERY_DATASET")
    return values


def _source_sql(spec: TableSpec, full: bool) -> str:
    prefix = "i." if spec.name == "recommendation_items" else ""
    columns = ", ".join(prefix + name for name, _ in spec.columns)
    query = f"SELECT {columns} FROM {spec.source}"
    if not full:
        query += f" WHERE {spec.change_time} >= %(start)s AND {spec.change_time} < %(end)s"
    return query + " ORDER BY " + ", ".join(prefix + key for key in spec.keys)


def _key_sql(spec: TableSpec) -> str:
    prefix = "i." if spec.name == "recommendation_items" else ""
    return "SELECT " + ", ".join(prefix + key for key in spec.keys) + " FROM " + spec.source


def _encode(row: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            output[key] = value.astimezone(timezone.utc).isoformat()
        elif isinstance(value, dict):
            output[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        elif value is None or isinstance(value, (str, int, float, bool)):
            output[key] = value
        else:
            output[key] = str(value)
    return output


def _load_query(client: bigquery.Client, connection: psycopg.Connection,
                query: str, params: dict[str, Any], table_id: str,
                schema: list[bigquery.SchemaField], location: str) -> int:
    client.delete_table(table_id, not_found_ok=True)
    client.create_table(bigquery.Table(table_id, schema=schema))
    count = 0
    with connection.cursor(name="raw_sync_cursor", row_factory=dict_row) as cursor:
        cursor.execute(query, params)
        while rows := cursor.fetchmany(1000):
            encoded = [_encode(row) for row in rows]
            client.load_table_from_json(
                encoded, table_id,
                job_config=bigquery.LoadJobConfig(schema=schema, write_disposition="WRITE_APPEND"),
                location=location,
            ).result()
            count += len(encoded)
    return count


def _target_exists(client: bigquery.Client, table_id: str) -> bool:
    try:
        client.get_table(table_id)
        return True
    except NotFound:
        return False


def _merge_sql(target: str, stage: str, spec: TableSpec) -> str:
    join = " AND ".join(f"T.{key} = S.{key}" for key in spec.keys)
    names = [name for name, _ in spec.columns]
    updates = ", ".join(f"{name} = S.{name}" for name in names if name not in spec.keys)
    return (f"MERGE `{target}` T USING `{stage}` S ON {join} "
            f"WHEN MATCHED THEN UPDATE SET {updates} "
            f"WHEN NOT MATCHED THEN INSERT ({', '.join(names)}) "
            f"VALUES ({', '.join('S.' + name for name in names)})")


def sync_table(name: str, start: datetime, end: datetime, full_refresh: bool = False) -> dict[str, int]:
    """Sync one table and verify source/target keys in a repeatable-read snapshot."""
    spec = TABLES[name]  # whitelist prevents SQL identifier injection
    database_url, project, dataset, location = _config()
    client = bigquery.Client(project=project)
    target = f"{project}.{dataset}.{name}"
    stage = f"{project}.{dataset}._stage_{name}"
    key_stage = f"{project}.{dataset}._keys_{name}"
    schema = [bigquery.SchemaField(column, kind) for column, kind in spec.columns]
    key_schema = [bigquery.SchemaField(key, "STRING") for key in spec.keys]
    existed = _target_exists(client, target)
    full = full_refresh or not existed
    params = {"start": start.astimezone(timezone.utc) - timedelta(days=1),
              "end": end.astimezone(timezone.utc)}
    try:
        with psycopg.connect(database_url) as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            changed = _load_query(client, connection, _source_sql(spec, full), params,
                                  stage, schema, location)
            # A complete key scan catches hard deletes that have no updated_at marker.
            source_count = _load_query(client, connection, _key_sql(spec), {},
                                       key_stage, key_schema, location)
        if full:
            client.query(f"CREATE OR REPLACE TABLE `{target}` AS SELECT * FROM `{stage}`",
                         location=location).result()
        else:
            client.query(_merge_sql(target, stage, spec), location=location).result()
            join = " AND ".join(f"T.{key} = K.{key}" for key in spec.keys)
            client.query(
                f"DELETE FROM `{target}` T WHERE NOT EXISTS "
                f"(SELECT 1 FROM `{key_stage}` K WHERE {join})", location=location
            ).result()
        key_names = ", ".join(spec.keys)
        check_sql = (f"SELECT COUNT(*) AS n, COUNT(DISTINCT TO_JSON_STRING(STRUCT({key_names}))) AS unique_n "
                     f"FROM `{target}`")
        result = list(client.query(check_sql, location=location).result())[0]
        difference_sql = (
            f"SELECT COUNT(*) AS n FROM ("
            f"(SELECT {key_names} FROM `{target}` EXCEPT DISTINCT "
            f"SELECT {key_names} FROM `{key_stage}`) UNION ALL "
            f"(SELECT {key_names} FROM `{key_stage}` EXCEPT DISTINCT "
            f"SELECT {key_names} FROM `{target}`))"
        )
        difference = list(client.query(difference_sql, location=location).result())[0].n
        if result.n != source_count or result.unique_n != result.n or difference:
            raise RuntimeError(
                f"{name}: source={source_count}, target={result.n}, "
                f"unique={result.unique_n}, key_difference={difference}"
            )
        return {"changed": changed, "source": source_count, "target": result.n}
    except Exception:
        # A failed first run must remain recognizable as needing a full load.
        if not existed:
            client.delete_table(target, not_found_ok=True)
        raise
    finally:
        client.delete_table(stage, not_found_ok=True)
        client.delete_table(key_stage, not_found_ok=True)
