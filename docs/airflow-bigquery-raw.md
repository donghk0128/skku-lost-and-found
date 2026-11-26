# Phase 2: PostgreSQL → Airflow → BigQuery Raw

## Current state and scope

This branch is stacked on `feat/event-logging` while its PR is under review. After
that PR merges, rebase this branch onto the updated `develop` before opening a
Phase 2 PR. No shared database migration, GCP resource, or EC2 deployment is
performed by this branch.

The DAG runs in local Docker for development. Its five allowlisted sources are
`event_logs`, `posts`, `return_pairs`, `recommendation_runs`, and
`recommendation_items`. BigQuery Raw keeps IDs, event/category/status values,
times, and ranking scores. It does **not** query passwords, tokens, email,
contact details, chat messages, post title/description, location text,
coordinates, image bytes or storage keys, embeddings, or search terms. The
event `properties` column is copied as JSON text; Phase 1 constrains its keys.
`return_pairs` includes pending rows, so downstream metrics must filter
`status = 'CONFIRMED'`.

## Agreed Raw deletion policy (2026-11-26)

For Phase 2, Supabase PostgreSQL is the authority for the five Raw tables.
When an individual source row is hard-deleted (including account withdrawal),
the next successful sync removes its matching BigQuery Raw row. This is an
eventual daily sync, not an immediate deletion request handler. A soft-deleted
post remains in Raw with `deleted_at`, matching its source state. There is no
exception in this pipeline that preserves a person's deleted event or
recommendation rows for analytics.

This decision covers the Raw tables only. Before Phase 3, define how derived
models and truly aggregated statistics respond to withdrawal; they must not
silently retain user-level rows. Also define a retention period and the
operational deletion deadline before deploying with real user data. BigQuery's
time-travel and fail-safe retention mean that deleting a row from the active
table is not the same as immediate physical erasure from every storage layer.

## Setup before a real run

1. Create or choose a GCP project and a BigQuery dataset. Choose one location
   and set it in `BIGQUERY_LOCATION`. Dataset creation, IAM changes, and any
   billed jobs should be reviewed with the team first.
2. Make a dedicated source role with `USAGE` on the application schema and
   `SELECT` on only the five source tables. Use an SSL connection string. The
   account should not own the tables or have write rights. A read-only
   transaction is also enforced by the loader.
3. Give the Airflow identity permission to run BigQuery jobs and read/write
   tables in the chosen dataset. Store its credentials outside Git. For this
   local Compose example, place the JSON credential at
   `airflow/secrets/gcp-sa.json`; ADC can be used in another deployment.
4. Copy `airflow/.env.example` to `airflow/.env` and fill in the real values.
   Both paths are Git-ignored. Never paste credentials into DAG code or logs.
5. From `airflow/`, run `docker compose up --build`. Airflow's local API UI is
   bound to `127.0.0.1:8080`. The DAG starts paused. Enable it only after
   checking the source role, BigQuery dataset, credentials, and expected cost.

The included Compose file is a development configuration. It is not the EC2
deployment plan. Airflow uses its own PostgreSQL metadata database; it is
separate from Supabase.

## Loading and recovery

The DAG is scheduled daily in UTC and has one active run at a time. On the
first run, a missing BigQuery table triggers a full load. A manual run with
`{"full_refresh": true}` also replaces all five Raw tables. Subsequent runs
read rows changed in the run's interval with a one-day overlap, then `MERGE`
by source key. Catchup is enabled, so missed daily intervals are scheduled
when Airflow resumes. Backfill or manual reruns use the same merge path.

The loader also scans **all source keys** in the same repeatable-read snapshot
and deletes BigQuery rows whose keys are no longer in PostgreSQL. This catches
hard deletes from account withdrawal, which timestamps alone cannot detect.
Soft-deleted posts remain in Raw with `deleted_at` set. Source and target row
counts, target key uniqueness, and both directions of key set difference are
checked after each table. A failed check fails the task and is retried; the
first run's target is removed on failure so the retry is full again.

The full key scan and BigQuery delete query cost more as tables grow. This is
deliberate for correctness at the project's current scale; a larger service
should use change data capture or deletion tombstones. Source data that arrives
after a snapshot is picked up by a later interval. If a past interval was
missed or a historical correction is suspected, rerun/backfill that interval
or trigger a full refresh. The SQL and BigQuery jobs are batch operations, not
real-time streaming.

## Validation before production

- Run against an isolated PostgreSQL fixture with the Phase 1 migrations.
- Verify empty, initial, incremental, duplicate rerun, correction, soft delete,
  hard delete, failed load/retry, and backfill cases.
- Compare source/target counts and keys; inspect the Airflow task logs and
  BigQuery job history. Record job bytes and storage size before estimating
  actual operating cost from the [BigQuery pricing page](https://cloud.google.com/bigquery/pricing).
- Keep the Phase 1 PR review and CI outcome separate from this branch's checks.

No live Supabase, BigQuery, or EC2 run has been performed in this workspace.
