import tempfile
import unittest
from pathlib import Path

from app.services.historical_capture_batch_service import (
    HistoricalCaptureBatchService,
)
from app.services.historical_operations_service import (
    HistoricalOperationsService,
)
from tests.helpers.database import create_test_session


FIXTURE = Path(
    "tests/fixtures/modus_capture/"
    "series14_week01_group_a.html"
)


class HistoricalOperationsServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results_html = FIXTURE.read_text(
            encoding="utf-8"
        )

    def setUp(self):
        self.db = create_test_session()
        self.service = HistoricalOperationsService()
        self.batch_service = HistoricalCaptureBatchService()

    def tearDown(self):
        self.db.close()

    def test_builds_without_existing_batch(self):
        with tempfile.TemporaryDirectory() as root:
            operations = self.service.build(
                self.db,
                root=root,
            )

        self.assertFalse(operations.batch_exists)
        self.assertIsNone(operations.batch)
        self.assertIsNone(operations.current_group)
        self.assertFalse(operations.capture_complete)
        self.assertEqual(
            operations.next_action,
            "Build a historical capture batch.",
        )

    def test_includes_current_batch_group(self):
        with tempfile.TemporaryDirectory() as root:
            self.batch_service.create(
                root=root,
                results_pages=[
                    (
                        "series14-week01-group-a.html",
                        self.results_html,
                    )
                ],
            )

            operations = self.service.build(
                self.db,
                root=root,
            )

        self.assertTrue(operations.batch_exists)
        self.assertIsNotNone(operations.current_group)
        self.assertEqual(
            operations.current_group.series_label,
            "Series 14",
        )
        self.assertEqual(
            operations.current_group.week_label,
            "Week 1",
        )
        self.assertEqual(
            operations.current_group.group,
            "Group A",
        )
        self.assertFalse(operations.capture_complete)
        self.assertIn(
            "Start capture for Series 14",
            operations.next_action,
        )

    def test_includes_import_and_warehouse_summaries(self):
        with tempfile.TemporaryDirectory() as root:
            operations = self.service.build(
                self.db,
                root=root,
            )

        self.assertFalse(
            operations.import_pipeline.queue_exists
        )
        self.assertIsNotNone(operations.warehouse)
        self.assertEqual(
            operations.warehouse.capture_summary["sessions"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
