"""Run against a disposable, migrated PostgreSQL database with SOURCE_DATABASE_URL set."""

import os
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from pipeline.sync import TABLES, _encode, _key_sql, _source_sql


@unittest.skipUnless(
    os.getenv("RUN_SOURCE_INTEGRATION_TESTS") == "1" and os.getenv("SOURCE_DATABASE_URL"),
    "needs explicit opt-in and disposable SOURCE_DATABASE_URL",
)
class SourceIntegrationTest(unittest.TestCase):
    def test_all_sources_and_incremental_changes(self):
        now = datetime.now(timezone.utc)
        ids = {name: uuid4() for name in (
            "user_a", "user_b", "lost", "found", "room", "pair", "run", "event",
            "impression", "visit")}
        with psycopg.connect(os.environ["SOURCE_DATABASE_URL"], autocommit=False) as conn:
            try:
                with conn.cursor() as cur:
                    for suffix in ("a", "b"):
                        cur.execute(
                            "INSERT INTO users (id,email,password_hash,nickname,email_verified_at,created_at,updated_at) "
                            "VALUES (%s,%s,'test','test-' || %s,%s,%s,%s)",
                            (ids[f"user_{suffix}"], f"{uuid4()}@example.test", uuid4().hex[:20], now, now, now),
                        )
                    for kind in ("lost", "found"):
                        cur.execute(
                            "INSERT INTO posts (id,author_id,post_type,title,description) "
                            "VALUES (%s,%s,%s,'test','test')",
                            (ids[kind], ids["user_a"], kind.upper()),
                        )
                    cur.execute(
                        "INSERT INTO chat_rooms (id,post_id,owner_id,requester_id) VALUES (%s,%s,%s,%s)",
                        (ids["room"], ids["lost"], ids["user_a"], ids["user_b"]),
                    )
                    cur.execute(
                        "INSERT INTO return_pairs (id,room_id,lost_post_id,found_post_id,proposed_by_id) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (ids["pair"], ids["room"], ids["lost"], ids["found"], ids["user_a"]),
                    )
                    cur.execute(
                        "INSERT INTO recommendation_runs (id,source_post_id,algorithm_version,fingerprint,filters,candidate_count) "
                        "VALUES (%s,%s,'test',%s,'{}',1)",
                        (ids["run"], ids["lost"], str(uuid4())),
                    )
                    cur.execute(
                        "INSERT INTO recommendation_items (run_id,candidate_post_id,rank,final_score,rule_score,"
                        "text_score,category_score,time_score,location_score,reasons) "
                        "VALUES (%s,%s,1,0.9,0.8,0.7,0.6,0.5,0.4,'{}')",
                        (ids["run"], ids["found"]),
                    )
                    cur.execute(
                        "INSERT INTO event_logs (id,user_id,event_type,occurred_at,properties) "
                        "VALUES (%s,%s,'test',%s,'{}')",
                        (ids["event"], ids["user_a"], now),
                    )
                    cur.execute(
                        "INSERT INTO event_logs (id,user_id,event_type,occurred_at,visit_id,"
                        "source_post_id,candidate_post_id,run_id,rank,properties) "
                        "VALUES (%s,%s,'recommendation_impression',%s,%s,%s,%s,%s,1,'{}')",
                        (ids["impression"], ids["user_a"], now, ids["visit"],
                         ids["lost"], ids["found"], ids["run"]),
                    )

                params = {"start": now - timedelta(minutes=1), "end": now + timedelta(minutes=1)}
                for name, spec in TABLES.items():
                    with self.subTest(table=name):
                        with conn.cursor(row_factory=dict_row) as cur:
                            cur.execute(_source_sql(spec, True), params)
                            rows = cur.fetchall()
                            self.assertTrue(rows)
                            self.assertEqual(set(rows[0]), {col for col, _ in spec.columns})
                            _encode(rows[0])
                            cur.execute(_source_sql(spec, False), params)
                            self.assertTrue(cur.fetchall())
                            cur.execute(_key_sql(spec))
                            self.assertTrue(cur.fetchall())

                with conn.cursor() as cur:
                    cur.execute("UPDATE posts SET status='COMPLETED', deleted_at=%s, updated_at=%s "
                                "WHERE id=%s", (now, now + timedelta(seconds=1), ids["lost"]))
                    cur.execute("UPDATE return_pairs SET status='CONFIRMED', confirmed_at=%s "
                                "WHERE id=%s", (now, ids["pair"]))
                    cur.execute("DELETE FROM event_logs WHERE id=%s", (ids["event"],))
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(_source_sql(TABLES["posts"], False),
                                {"start": now, "end": now + timedelta(minutes=1)})
                    self.assertTrue(any(row["id"] == ids["lost"] and row["status"] == "COMPLETED"
                                        and row["deleted_at"] is not None
                                        for row in cur.fetchall()))
                    cur.execute(_source_sql(TABLES["return_pairs"], False),
                                {"start": now - timedelta(minutes=1),
                                 "end": now + timedelta(minutes=1)})
                    self.assertTrue(any(row["id"] == ids["pair"] and row["status"] == "CONFIRMED"
                                        for row in cur.fetchall()))
                    cur.execute(_key_sql(TABLES["event_logs"]))
                    self.assertNotIn(ids["event"], [row["id"] for row in cur.fetchall()])
                # Model account/post cleanup before a source hard delete.
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM event_logs WHERE id=%s", (ids["impression"],))
                    cur.execute("DELETE FROM recommendation_items WHERE candidate_post_id=%s",
                                (ids["found"],))
                    cur.execute("DELETE FROM posts WHERE id=%s", (ids["found"],))
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(_key_sql(TABLES["posts"]))
                    self.assertNotIn(ids["found"], [row["id"] for row in cur.fetchall()])
                    cur.execute(_key_sql(TABLES["return_pairs"]))
                    self.assertNotIn(ids["pair"], [row["id"] for row in cur.fetchall()])
            finally:
                conn.rollback()


if __name__ == "__main__":
    unittest.main()
