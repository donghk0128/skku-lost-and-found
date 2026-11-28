"""Scheduled and CLI-triggered runs both have a usable extraction window."""

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from dags.skku_raw_sync import _sync_window


class SyncWindowTest(unittest.TestCase):
    def test_scheduled_run_uses_airflow_interval(self):
        end = datetime(2026, 11, 27, tzinfo=timezone.utc)
        start = end - timedelta(days=1)
        context = {"dag_run": SimpleNamespace(run_after=end),
                   "data_interval_start": start, "data_interval_end": end}
        self.assertEqual(_sync_window(context), (start, end))

    def test_cli_manual_run_without_interval_uses_trigger_time(self):
        triggered_at = datetime(2026, 11, 27, 9, 36, tzinfo=timezone.utc)
        context = {"dag_run": SimpleNamespace(run_after=triggered_at)}
        self.assertEqual(_sync_window(context), (triggered_at, triggered_at))


if __name__ == "__main__":
    unittest.main()
