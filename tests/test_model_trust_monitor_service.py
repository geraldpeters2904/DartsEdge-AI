import unittest

from app.prediction_config import (
    ACTIVE_PREDICTION_MODEL_NAME,
)
from unittest.mock import MagicMock, patch

from app.services.model_trust_monitor_service import (
    ModelTrustMonitor,
)


class ModelTrustMonitorTests(
    unittest.TestCase
):
    def setUp(self):
        self.monitor = ModelTrustMonitor(
            interval_seconds=300,
            initial_delay_seconds=0,
        )

    def test_session_creation_failure_is_recorded(self):
        with patch(
            "app.services.model_trust_monitor_service.SessionLocal",
            side_effect=RuntimeError("database unavailable"),
        ):
            monitor = ModelTrustMonitor(
                interval_seconds=60,
                initial_delay_seconds=0,
            )
            status = monitor.run_once()

        self.assertEqual(status.runs, 1)
        self.assertEqual(status.failures, 1)
        self.assertEqual(
            status.last_message,
            "Model trust refresh failed.",
        )
        self.assertEqual(
            status.last_error,
            "database unavailable",
        )

    def test_stop_waits_for_background_thread_to_exit(self):
        monitor = ModelTrustMonitor(
            interval_seconds=300,
            initial_delay_seconds=60,
        )

        monitor.start()
        thread = monitor._thread

        self.assertIsNotNone(thread)
        self.assertTrue(thread.is_alive())

        status = monitor.stop()

        self.assertFalse(status.running)
        self.assertFalse(thread.is_alive())

    @patch(
        "app.services.model_trust_monitor_service."
        "build_model_trust_report"
    )
    @patch(
        "app.services.model_trust_monitor_service."
        "SessionLocal"
    )
    def test_run_once_stores_report(
        self,
        session_local,
        build_report,
    ):
        db = MagicMock()
        session_local.return_value = db

        report = MagicMock()
        report.trust_score = 84.5
        report.trust_grade = "A"
        report.sample_size = 3000

        build_report.return_value = report

        status = self.monitor.run_once()

        self.assertEqual(
            status.runs,
            1,
        )
        self.assertEqual(
            status.failures,
            0,
        )
        self.assertEqual(
            status.trust_score,
            84.5,
        )
        self.assertEqual(
            status.trust_grade,
            "A",
        )
        self.assertEqual(
            status.sample_size,
            3000,
        )
        self.assertIs(
            self.monitor.latest_report(),
            report,
        )

        build_report.assert_called_once_with(
            db,
            model_name=ACTIVE_PREDICTION_MODEL_NAME,
            offset=500,
            limit=3000,
        )

        db.close.assert_called_once()

    @patch(
        "app.services.model_trust_monitor_service."
        "build_model_trust_report"
    )
    @patch(
        "app.services.model_trust_monitor_service."
        "SessionLocal"
    )
    def test_failure_is_recorded(
        self,
        session_local,
        build_report,
    ):
        db = MagicMock()
        session_local.return_value = db

        build_report.side_effect = RuntimeError(
            "boom"
        )

        status = self.monitor.run_once()

        self.assertEqual(
            status.runs,
            1,
        )
        self.assertEqual(
            status.failures,
            1,
        )
        self.assertEqual(
            status.last_error,
            "boom",
        )
        self.assertIsNone(
            self.monitor.latest_report()
        )

        db.close.assert_called_once()

    def test_initial_status_has_no_report(self):
        status = self.monitor.status()

        self.assertFalse(
            status.running
        )
        self.assertEqual(
            status.runs,
            0,
        )
        self.assertIsNone(
            status.trust_score
        )
        self.assertIsNone(
            self.monitor.latest_report()
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
