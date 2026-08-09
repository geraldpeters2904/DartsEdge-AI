
import unittest

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


if __name__ == "__main__":
    unittest.main()
