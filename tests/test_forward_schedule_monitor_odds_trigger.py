import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.forward_schedule_monitor_service import (
    ForwardScheduleMonitor,
)


class ForwardScheduleMonitorOddsTriggerTests(
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
    def test_zero_future_fixtures_records_no_capture(
        self,
        discovery,
        trigger,
    ):
        discovery.return_value = SimpleNamespace(
            series_label="Series 15",
            week_label="Week 2",
            future_fixtures=0,
            message=(
                "No future MODUS fixtures are currently "
                "published."
            ),
        )

        trigger.consider.return_value = (
            SimpleNamespace(
                triggered=False,
                ready=True,
                captured_at=None,
                extracted_prices=0,
                stored_prices=0,
                message=(
                    "Odds capture not required because "
                    "no future fixtures are available."
                ),
                error=None,
            )
        )

        monitor = ForwardScheduleMonitor(
            interval_seconds=900,
            initial_delay_seconds=0,
        )

        status = monitor.run_once()

        trigger.consider.assert_called_once_with(
            future_fixtures=0
        )

        self.assertEqual(
            status.future_fixtures,
            0,
        )

        self.assertFalse(
            status.odds_capture_triggered
        )

        self.assertTrue(
            status.odds_capture_ready
        )

        self.assertEqual(
            status.odds_prices_extracted,
            0,
        )

        self.assertEqual(
            status.odds_prices_stored,
            0,
        )

        self.assertIsNone(
            status.odds_capture_error
        )


if __name__ == "__main__":
    unittest.main()
