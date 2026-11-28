"""A failed dbt build must never expose an unverified dashboard state."""

import subprocess
import unittest
from unittest.mock import call, patch

from pipeline.build import build_marts


class BuildGateTest(unittest.TestCase):
    def test_failed_build_stays_unavailable(self):
        with (patch("pipeline.build.record_status") as status,
              patch("pipeline.build.subprocess.run",
                    side_effect=subprocess.CalledProcessError(1, "dbt"))):
            with self.assertRaises(subprocess.CalledProcessError):
                build_marts()
        self.assertEqual(status.call_args_list, [call("RUNNING"), call("FAILED")])

    def test_successful_build_becomes_ready(self):
        with (patch("pipeline.build.record_status") as status,
              patch("pipeline.build.subprocess.run") as runner):
            build_marts()
        self.assertEqual(status.call_args_list, [call("RUNNING"), call("READY")])
        self.assertTrue(runner.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()
