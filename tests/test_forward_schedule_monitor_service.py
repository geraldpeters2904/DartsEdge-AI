
import unittest
from datetime import datetime

from app.services.forward_schedule_monitor_service import (
    ForwardScheduleMonitor,
)


class ForwardScheduleMonitorTests(unittest.TestCase):
    def test_initial_status_is_stopped(self):
        monitor = ForwardScheduleMonitor(
            interval_seconds=60,
            initial_delay_seconds=0,
        )
        self.assertFalse(monitor.status().running)
        self.assertEqual(monitor.status().runs, 0)

    def test_start_and_stop(self):
        monitor = ForwardScheduleMonitor(
            interval_seconds=60,
            initial_delay_seconds=60,
        )
        self.assertTrue(monitor.start().running)
        self.assertFalse(monitor.stop().running)


    def test_next_run_is_after_last_run_by_interval(self):
        monitor = ForwardScheduleMonitor(
            interval_seconds=900,
            initial_delay_seconds=60,
        )

        module = __import__(
            "app.services.forward_schedule_monitor_service",
            fromlist=["run_forward_schedule_discovery"],
        )
        original = module.run_forward_schedule_discovery

        class Report:
            series_label = "Series 15"
            week_label = "Week 1"
            future_fixtures = 0
            message = "No future fixtures."

        module.run_forward_schedule_discovery = lambda: Report()

        try:
            with monitor._lock:
                monitor._copy(running=True)
            status = monitor.run_once()
        finally:
            module.run_forward_schedule_discovery = original

        last_run = datetime.fromisoformat(status.last_run_at)
        next_run = datetime.fromisoformat(status.next_run_at)

        self.assertGreater(next_run, last_run)
        self.assertAlmostEqual(
            (next_run - last_run).total_seconds(),
            900.0,
            delta=1.0,
        )


if __name__ == "__main__":
    unittest.main()
