
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


    def test_run_once_skips_when_cycle_already_running(self):
        monitor = getattr(self, "monitor", None)
        if monitor is None:
            monitor_class = type(
                self
            ).__module__.split(".")[-1]
            if monitor_class == "test_live_edge_monitor_service":
                monitor = LiveEdgeMonitor(
                    interval_seconds=60,
                    initial_delay_seconds=0,
                )

        acquired = monitor._run_lock.acquire(
            blocking=False
        )
        self.assertTrue(acquired)

        try:
            before = monitor.status()
            status = monitor.run_once()
        finally:
            monitor._run_lock.release()

        self.assertEqual(
            status.runs,
            before.runs,
        )
        self.assertEqual(
            status.failures,
            before.failures,
        )
        self.assertEqual(
            status.last_message,
            before.last_message,
        )
        self.assertEqual(
            status.last_error,
            before.last_error,
        )



if __name__ == "__main__":
    unittest.main()
