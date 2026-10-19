import unittest
from types import SimpleNamespace

from app.services.mission_control_service import _build_alerts


class MissionControlCaptureAlertTests(unittest.TestCase):

    def setUp(self):
        self.dashboard = {
            "results_awaiting": [],
            "database_health": 100,
            "open_paper_trades": 0,
        }

    def test_failed_bookmaker_capture_creates_alert(self):
        status = SimpleNamespace(
            last_results=(
                SimpleNamespace(
                    name="bookmaker-capture",
                    success=False,
                    message="Paddy Power event capture partially completed: 1 event(s) failed.",
                ),
            ),
        )

        alerts = _build_alerts(self.dashboard, sync_status=status)

        self.assertEqual(alerts[0]["level"], "warning")
        self.assertIn("Paddy Power", alerts[0]["title"])
        self.assertIn("1 event(s) failed", alerts[0]["message"])

    def test_successful_bookmaker_capture_creates_no_failure_alert(self):
        status = SimpleNamespace(
            last_results=(
                SimpleNamespace(
                    name="bookmaker-capture",
                    success=True,
                    message="Paddy Power discovered event capture completed.",
                ),
            ),
        )

        alerts = _build_alerts(self.dashboard, sync_status=status)

        self.assertEqual(alerts[0]["title"], "No urgent actions")

    def test_no_sync_results_creates_no_failure_alert(self):
        status = SimpleNamespace(last_results=())

        alerts = _build_alerts(self.dashboard, sync_status=status)

        self.assertEqual(alerts[0]["title"], "No urgent actions")


if __name__ == "__main__":
    unittest.main()
