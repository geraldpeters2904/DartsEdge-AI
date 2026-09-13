import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.forward_schedule_monitor_service import (
    ForwardScheduleMonitor,
)


class ForwardScheduleMonitorCatchupTests(unittest.TestCase):

    @patch(
        "app.services.forward_schedule_monitor_service."
        "run_forward_fixture_catchup_once"
    )
    @patch(
        "app.services.forward_schedule_monitor_service."
        "run_forward_schedule_discovery"
    )
    def test_successful_discovery_runs_fixture_catchup(
        self,
        discovery,
        catchup,
    ):
        discovery.return_value = SimpleNamespace(
            series_label="Series 26",
            week_label="Week 196",
            future_fixtures=9,
            message="Discovery complete.",
            target_results=(),
        )

        catchup.return_value = SimpleNamespace(
            candidates=0,
            attempted=0,
            completed=0,
            unchanged=0,
            failed=0,
            message="No stale fixtures.",
        )

        monitor = ForwardScheduleMonitor(
            interval_seconds=900,
            initial_delay_seconds=0,
            enable_odds_capture_trigger=False,
        )

        status = monitor.run_once()

        discovery.assert_called_once_with()
        catchup.assert_called_once_with()

        self.assertEqual(status.runs, 1)
        self.assertEqual(status.failures, 0)
        self.assertIsNone(status.last_error)


if __name__ == "__main__":
    unittest.main()
