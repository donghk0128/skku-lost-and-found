"""Run dbt after all Raw tasks pass and publish a dashboard quality gate."""

from __future__ import annotations

import os
import re
import subprocess
from uuid import uuid4

from google.cloud import bigquery


def record_status(state: str) -> None:
    project = os.environ["GCP_PROJECT_ID"]
    dataset = os.environ["BIGQUERY_ANALYTICS_DATASET"]
    location = os.environ["BIGQUERY_LOCATION"]
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project):
        raise ValueError("Invalid GCP_PROJECT_ID")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,1023}", dataset):
        raise ValueError("Invalid BIGQUERY_ANALYTICS_DATASET")
    client = bigquery.Client(project=project)
    table = f"{project}.{dataset}.pipeline_status"
    # The analytics dataset must be provisioned before this task is enabled.
    client.get_dataset(f"{project}.{dataset}")
    client.query(
        f"CREATE TABLE IF NOT EXISTS `{table}` "
        "(run_id STRING, state STRING, recorded_at TIMESTAMP)",
        location=location,
    ).result()
    client.query(
        f"INSERT INTO `{table}` (run_id, state, recorded_at) "
        "VALUES (@run_id, @state, CURRENT_TIMESTAMP())",
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("run_id", "STRING", str(uuid4())),
            bigquery.ScalarQueryParameter("state", "STRING", state),
        ]),
        location=location,
    ).result()


def build_marts() -> None:
    record_status("RUNNING")
    try:
        subprocess.run(
            ["dbt", "build", "--project-dir", "/opt/airflow/dbt",
             "--profiles-dir", "/opt/airflow/dbt", "--target", "prod",
             "--target-path", "/tmp/dbt-target", "--log-path", "/tmp/dbt-logs",
             "--no-partial-parse"],
            check=True,
            timeout=3600,
        )
    except Exception:
        record_status("FAILED")
        raise
    record_status("READY")
