import tempfile
import unittest
from pathlib import Path

from app.services.modus_capture_session_service import (
    ModusCaptureSessionService,
)
from app.services.operations_dashboard_service import (
    OperationsDashboardService,
)
from tests.helpers.database import create_test_session


FIXTURE = Path(
    "tests/fixtures/modus_capture/series14_week01_group_a.html"
)


class OperationsDashboardServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results_html = FIXTURE.read_text(encoding="utf-8")

    def setUp(self):
        self.db = create_test_session()
        self.service = OperationsDashboardService()
        self.capture_service = ModusCaptureSessionService()

    def tearDown(self):
        self.db.close()

    def test_builds_without_capture_sessions(self):
        with tempfile.TemporaryDirectory() as root:
            dashboard = self.service.build(
                self.db,
                capture_root=root,
            )

        self.assertFalse(dashboard.capture_running)
        self.assertIsNone(dashboard.active_capture)
        self.assertIsNone(dashboard.next_match_id)
        self.assertEqual(
            dashboard.warehouse.capture_summary["sessions"],
            0,
        )

    def test_includes_latest_unfinished_capture(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "Series_14" / "Week_01" / "Group_A"

            self.capture_service.create_session(
                results_filename="results.html",
                results_html=self.results_html,
                destination_folder=folder,
            )

            dashboard = self.service.build(
                self.db,
                capture_root=root,
            )

        self.assertTrue(dashboard.capture_running)
        self.assertIsNotNone(dashboard.active_capture)
        self.assertEqual(
            dashboard.active_capture.series_label,
            "Series 14",
        )
        self.assertEqual(
            dashboard.active_capture.week_label,
            "Week 1",
        )
        self.assertEqual(
            dashboard.active_capture.group,
            "Group A",
        )
        self.assertIsNotNone(dashboard.next_match_id)
        self.assertEqual(
            dashboard.warehouse.capture_summary["sessions"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
