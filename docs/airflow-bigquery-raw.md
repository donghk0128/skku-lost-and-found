# Phase 2: PostgreSQL → Airflow → BigQuery Raw

## Current state and scope

The Phase 1 event logging and return pair changes are merged into `develop`.
The Phase 2 branch has not been submitted as a PR. An EC2 trial runs from a
detached checkout of this branch; this does not make the Airflow stack part of
the regular backend deployment.

The DAG runs in Docker on the EC2 trial host. Its five allowlisted sources are
`event_logs`, `posts`, `return_pairs`, `recommendation_runs`, and
`recommendation_items`. BigQuery Raw keeps IDs, event/category/status values,
times, and ranking scores. It does **not** query passwords, tokens, email,
contact details, chat messages, post title/description, location text,
coordinates, image bytes or storage keys, embeddings, or search terms. The
event `properties` column is copied as JSON text; Phase 1 constrains its keys.
`return_pairs` includes pending rows, so downstream metrics must filter
`status = 'CONFIRMED'`.

The selected BigQuery destination is
`project-2d59f32a-6674-4fa9-9a4.skku_finder_raw` in `asia-northeast3` (Seoul).
The dataset location was checked before the first load.

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
3. Grant the `skku-airflow-loader` service account BigQuery Job User on the
   project and BigQuery Data Editor on only the Raw dataset. The project policy
   blocks user-managed service account keys. Do not disable it. For local
   development, install the Google Cloud CLI and grant the signed-in developer
   Service Account Token Creator on this service account only. Run
   `gcloud auth application-default login --impersonate-service-account
   skku-airflow-loader@project-2d59f32a-6674-4fa9-9a4.iam.gserviceaccount.com`.
   The CLI creates a local ADC file using short-lived impersonation tokens.
   Point `GCP_ADC_FILE` in the ignored `.env` to that host file. Compose mounts
   it read-only inside Airflow. The ADC file still contains a user refresh
   credential and must not be shared or committed. The EC2 trial uses
   AWS-to-GCP Workload Identity Federation instead of a JSON key. The EC2 role
   `skku-airflow-ec2` is restricted to impersonating `skku-airflow-loader`
   through the `skku-airflow` pool and `aws-ec2` provider. Its credential
   configuration was generated with `--aws --enable-imdsv2`, copied to the
   ignored `airflow/secrets/` directory, and mounted through `GCP_ADC_FILE`.
4. Copy `airflow/.env.example` to `airflow/.env` and fill in the real values.
   Both paths are Git-ignored. Never paste credentials into DAG code or logs.
   Generate `AIRFLOW_JWT_SECRET` once with `openssl rand -hex 32`; the API
   server and scheduler must share it to authenticate task execution. The
   scheduler reaches the separate API server through the Compose service name.
5. From `airflow/`, run `docker compose up --build`. Airflow's local API UI is
   bound to `127.0.0.1:8080`. The DAG starts paused. Enable it only after
   checking the source role, BigQuery dataset, credentials, and expected cost.

The included Compose file is a trial configuration, not a hardened EC2
deployment plan. Airflow uses its own PostgreSQL metadata database, separate
from Supabase. On EC2, the host `airflow/logs` directory had to be owned by the
image's Airflow user (`50000:0`) before the dag processor could create logs.
The scheduler needs `AIRFLOW__CORE__EXECUTION_API_SERVER_URL` pointing at the
separate API server, and all Airflow services need the same JWT secret. Without
these settings, task attempts failed before entering the sync function.

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

## Validation and remaining checks

- The five source queries were exercised on an isolated PostgreSQL container
  after applying migrations through `0018_return_pairs`. The integration test
  covered full and incremental extraction, post updates, and hard-deleted event
  keys; its fixture transaction was rolled back. The test requires explicit
  `RUN_SOURCE_INTEGRATION_TESTS=1` and a disposable `SOURCE_DATABASE_URL`.
- Local impersonated ADC could read the target BigQuery dataset and submit a
  zero-byte dry-run query from the Airflow image. This did not create Raw tables.
- On 2026-11-27 KST, the EC2 trial used the read-only Supabase role to execute
  all five allowlisted source queries. AWS-to-GCP federation read the target
  dataset and submitted a zero-byte BigQuery query job from the Airflow image.
- The first scheduled run (`2026-11-25` UTC) created all five Raw tables and
  succeeded. The next scheduled run (`2026-11-26` UTC) exercised the incremental
  path and also succeeded. Each task checks source/target counts, target key
  uniqueness, and key-set differences. Independent metadata row counts matched:

  | Table | Supabase | BigQuery |
  | --- | ---: | ---: |
  | `event_logs` | 0 | 0 |
  | `posts` | 83 | 83 |
  | `return_pairs` | 0 | 0 |
  | `recommendation_runs` | 5 | 5 |
  | `recommendation_items` | 103 | 103 |

- The API health endpoint returned HTTP 200 after both runs. On the `t3.small`
  with 2 GiB swap and a 20 GiB root volume, the post-load snapshot showed
  611 MiB available RAM, 269 MiB swap in use, 5.4 GiB disk free, and no Airflow
  container restarts or OOM kills. This supports a trial at current data size,
  not a guarantee under growth or after reboot.
- Still verify an actual updated row, duplicate rerun, correction, soft and
  hard delete, nonempty `event_logs` and `return_pairs`, and recovery from a
  failed data load. The next daily schedule and reboot persistence also need
  observation. Do these checks with isolated fixtures where they would change
  shared application data.
- Inspect Airflow task logs and BigQuery job history. Record job bytes and
  storage size before estimating ongoing cost from the
  [BigQuery pricing page](https://cloud.google.com/bigquery/pricing).
