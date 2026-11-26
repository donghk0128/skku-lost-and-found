"""Contract checks for the explicit Raw export boundary."""

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from pipeline.sync import TABLES, _encode, _key_sql, _merge_sql, _source_sql


class ExportContractTest(unittest.TestCase):
    def test_only_expected_sources_and_no_sensitive_columns(self):
        self.assertEqual(set(TABLES), {
            "event_logs", "posts", "return_pairs", "recommendation_runs",
            "recommendation_items",
        })
        forbidden = {"email", "content", "title", "description", "storage_key",
                     "latitude", "longitude", "location_text", "embedding", "filters"}
        for spec in TABLES.values():
            with self.subTest(table=spec.name):
                self.assertFalse({name for name, _ in spec.columns} & forbidden)
                self.assertTrue(set(spec.keys) <= {name for name, _ in spec.columns})
                self.assertIn("ORDER BY", _source_sql(spec, False))
                self.assertIn("%(start)s", _source_sql(spec, False))
                self.assertNotIn("%(start)s", _source_sql(spec, True))

    def test_recommendation_items_use_run_time_and_composite_key(self):
        spec = TABLES["recommendation_items"]
        self.assertIn("JOIN recommendation_runs", _source_sql(spec, False))
        self.assertIn("r.generated_at", _source_sql(spec, False))
        self.assertIn("i.candidate_post_id", _key_sql(spec))
        merge = _merge_sql("p.d.t", "p.d.s", spec)
        self.assertIn("T.run_id = S.run_id AND T.candidate_post_id = S.candidate_post_id", merge)

    def test_timestamp_uuid_and_bounded_properties_are_serialized(self):
        uid = uuid4()
        encoded = _encode({"id": uid, "occurred_at": datetime(2026, 11, 25, tzinfo=timezone.utc),
                           "properties": {"screen": "home"}})
        self.assertEqual(encoded["id"], str(uid))
        self.assertTrue(encoded["occurred_at"].endswith("+00:00"))
        self.assertEqual(encoded["properties"], '{"screen": "home"}')


if __name__ == "__main__":
    unittest.main()
