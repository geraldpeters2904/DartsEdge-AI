
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


    def test_session_creation_failure_is_recorded(self):
        from unittest.mock import patch

        monitor = LiveEdgeMonitor(
            interval_seconds=60,
            initial_delay_seconds=0,
        )

        with patch(
            "app.services.live_edge_monitor_service.SessionLocal",
            side_effect=RuntimeError("database unavailable"),
        ):
            status = monitor.run_once()

        self.assertEqual(status.runs, 1)
        self.assertEqual(status.failures, 1)
        self.assertEqual(
            status.last_message,
            "Live Edge monitor cycle failed.",
        )
        self.assertEqual(
            status.last_error,
            "database unavailable",
        )

    def test_stop_waits_for_background_thread_to_exit(self):
        monitor = LiveEdgeMonitor(
            interval_seconds=60,
            initial_delay_seconds=60,
        )

        monitor.start()
        thread = monitor._thread

        self.assertIsNotNone(thread)
        self.assertTrue(thread.is_alive())

        status = monitor.stop()

        self.assertFalse(status.running)
        self.assertFalse(thread.is_alive())

    def test_stop_waits_for_active_cycle_to_finish(self):
        import threading

        monitor = LiveEdgeMonitor(
            interval_seconds=60,
            initial_delay_seconds=0,
        )

        entered = threading.Event()
        release = threading.Event()

        def controlled_cycle():
            entered.set()
            release.wait(timeout=1.0)
            return monitor.status()

        monitor._run_once_locked = controlled_cycle

        monitor.start()
        self.assertTrue(entered.wait(timeout=1.0))

        timer = threading.Timer(0.05, release.set)
        timer.start()

        status = monitor.stop()
        timer.join()

        self.assertFalse(status.running)
        self.assertFalse(monitor._thread.is_alive())

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
