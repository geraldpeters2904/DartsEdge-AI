import unittest
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
            model_name="transparent-v3.3",
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


if __name__ == "__main__":
    unittest.main()
