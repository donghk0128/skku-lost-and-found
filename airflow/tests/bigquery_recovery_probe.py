"""Exercise same-window replay and partial BigQuery recovery in a test dataset.

Run only with a read-only source connection and a disposable BigQuery dataset.
The probe creates a uniquely named target table and removes it on exit.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from pipeline import sync


def main() -> None:
    project = os.environ["GCP_PROJECT_ID"]
    dataset = os.environ["BIGQUERY_DATASET"]
    location = os.environ["BIGQUERY_LOCATION"]
    if "_test_" not in dataset:
        raise ValueError("Recovery probe requires an isolated _test_ dataset")

    name = f"posts_recovery_{uuid4().hex[:12]}"
    target = f"{project}.{dataset}.{name}"
    client = bigquery.Client(project=project)
    try:
        client.get_table(target)
    except NotFound:
        pass
    else:
        raise RuntimeError(f"Probe target already exists: {target}")

    stamp = datetime.now(timezone.utc)
    stale_id = str(uuid4())
    print(f"probe_table={target}", flush=True)
    sync.TABLES[name] = sync.TABLES["posts"]
    try:
        first = sync.sync_table(name, stamp, stamp, full_refresh=True)
        replay = sync.sync_table(name, stamp, stamp)
        if first["target"] != replay["target"]:
            raise AssertionError(f"Same-window row count changed: {first} -> {replay}")
        print(f"same_window_replay=ok rows={replay['target']}", flush=True)

        client.query(
            f"INSERT INTO `{target}` (id) VALUES (@stale_id)",
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("stale_id", "STRING", stale_id)
            ]),
            location=location,
        ).result()

        state = {"merge_seen": False, "delete_failed": False}

        class FailBeforeDelete:
            def __init__(self, real: bigquery.Client):
                self.real = real

            def __getattr__(self, key: str):
                return getattr(self.real, key)

            def query(self, sql: str, **kwargs):
                if sql.startswith(f"MERGE `{target}`"):
                    state["merge_seen"] = True
                if sql.startswith(f"DELETE FROM `{target}`") and not state["delete_failed"]:
                    state["delete_failed"] = True
                    raise RuntimeError("Injected failure after BigQuery MERGE, before DELETE")
                return self.real.query(sql, **kwargs)

        with patch.object(sync.bigquery, "Client", return_value=FailBeforeDelete(client)):
            try:
                sync.sync_table(name, stamp, stamp)
            except RuntimeError as exc:
                if "Injected failure" not in str(exc):
                    raise
            else:
                raise AssertionError("Expected injected failure was not raised")
        if not all(state.values()):
            raise AssertionError(f"BigQuery MERGE/DELETE boundary not reached: {state}")

        stale_count = list(client.query(
            f"SELECT COUNTIF(id = @stale_id) AS n FROM `{target}`",
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("stale_id", "STRING", stale_id)
            ]),
            location=location,
        ).result())[0].n
        if stale_count != 1:
            raise AssertionError("Stale test row did not remain after injected failure")
        print("partial_failure=observed stale_row=1", flush=True)

        recovered = sync.sync_table(name, stamp, stamp)
        if recovered["target"] != first["target"]:
            raise AssertionError(f"Recovered count differs from source snapshot: {recovered}")
        stale_count = list(client.query(
            f"SELECT COUNTIF(id = @stale_id) AS n FROM `{target}`",
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("stale_id", "STRING", stale_id)
            ]),
            location=location,
        ).result())[0].n
        if stale_count != 0:
            raise AssertionError("Retry left the stale test row in BigQuery")
        print(f"partial_recovery=ok rows={recovered['target']} stale_row=0", flush=True)
    finally:
        sync.TABLES.pop(name, None)
        client.delete_table(target, not_found_ok=True)
        print(f"probe_table_removed={target}", flush=True)


if __name__ == "__main__":
    main()
