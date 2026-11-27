"""Daily PostgreSQL -> BigQuery raw sync. Trigger with full_refresh=true initially."""

from datetime import datetime, timezone

from airflow.sdk import dag, get_current_context, task

from pipeline.sync import TABLES, sync_table


def _sync_window(context):
    start = context.get("data_interval_start")
    end = context.get("data_interval_end")
    if start is None or end is None:
        # Airflow 3 CLI manual runs can omit the data interval entirely.
        # sync_table applies a one-day overlap before this trigger time.
        triggered_at = getattr(context["dag_run"], "run_after", None) or datetime.now(timezone.utc)
        return triggered_at, triggered_at
    return start, end


@dag(
    dag_id="skku_raw_sync",
    schedule="@daily",
    start_date=datetime(2026, 11, 25, tzinfo=timezone.utc),
    catchup=True,
    max_active_runs=1,
    max_active_tasks=1,
    tags=["skku", "raw"],
)
def skku_raw_sync():
    @task(retries=2)
    def sync(name: str) -> dict[str, int]:
        context = get_current_context()
        dag_run = context["dag_run"]
        full_refresh = bool((dag_run.conf or {}).get("full_refresh", False))
        start, end = _sync_window(context)
        return sync_table(name, start, end, full_refresh)

    for table_name in TABLES:
        sync.override(task_id=f"sync_{table_name}")(table_name)


skku_raw_sync()
