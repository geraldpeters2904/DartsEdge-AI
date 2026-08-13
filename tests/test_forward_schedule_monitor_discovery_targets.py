import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.forward_schedule_monitor_service import (
    ForwardScheduleMonitor,
)


class ForwardScheduleMonitorDiscoveryTargetTests(
    unittest.TestCase
):
    @patch(
        "app.services.forward_schedule_monitor_service."
        "automatic_odds_capture_trigger"
    )
    @patch(
        "app.services.forward_schedule_monitor_service."
        "run_forward_schedule_discovery"
    )
    def test_monitor_retains_latest_discovery_targets(
        self,
        discovery,
        trigger,
    ):
        target = SimpleNamespace(
            group="Group A",
            state="IMPORTED",
            fixture_count=12,
            error=None,
            message="Imported.",
        )

        discovery.return_value = SimpleNamespace(
            series_label="Series 15",
            week_label="Week 2",
            future_fixtures=2,
            message="Found fixtures.",
            target_results=(target,),
        )

        trigger.consider.return_value = SimpleNamespace(
            triggered=True,
            ready=True,
            captured_at="2026-08-13T10:00:00",
            extracted_prices=2,
            stored_prices=2,
            message="Captured.",
            error=None,
        )

        monitor = ForwardScheduleMonitor(
            interval_seconds=900,
            initial_delay_seconds=0,
        )

        status = monitor.run_once()

        self.assertEqual(
            len(status.discovery_targets),
            1,
        )
        self.assertEqual(
            status.discovery_targets[0].group,
            "Group A",
        )
        self.assertEqual(
            status.discovery_targets[0].state,
            "IMPORTED",
        )


if __name__ == "__main__":
    unittest.main()
