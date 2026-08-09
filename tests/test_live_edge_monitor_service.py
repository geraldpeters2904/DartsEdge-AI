
import unittest

from app.services.live_edge_monitor_service import (
    LiveEdgeMonitor,
)


class LiveEdgeMonitorTests(unittest.TestCase):
    def test_initial_status_is_stopped(self):
        monitor = LiveEdgeMonitor(
            interval_seconds=60,
            initial_delay_seconds=0,
        )

        self.assertFalse(
            monitor.status().running
        )

        self.assertEqual(
            monitor.status().runs,
            0,
        )

    def test_start_stop(self):
        monitor = LiveEdgeMonitor(
            interval_seconds=60,
            initial_delay_seconds=60,
        )

        self.assertTrue(
            monitor.start().running
        )

        self.assertFalse(
            monitor.stop().running
        )


if __name__ == "__main__":
    unittest.main()
