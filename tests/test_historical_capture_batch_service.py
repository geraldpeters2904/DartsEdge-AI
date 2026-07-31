import json
import tempfile
import unittest
from pathlib import Path

from app.services.historical_capture_batch_service import (
    BATCH_FILENAME,
    HistoricalCaptureBatchService,
)


FIXTURE = Path(
    "tests/fixtures/modus_capture/"
    "series14_week01_group_a.html"
)


class HistoricalCaptureBatchServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.group_a_html = FIXTURE.read_text(
            encoding="utf-8"
        )

    def setUp(self):
        self.service = HistoricalCaptureBatchService()

    def test_creates_persistent_batch_and_capture_session(self):
        with tempfile.TemporaryDirectory() as root:
            batch = self.service.create(
                root=root,
                results_pages=[
                    (
                        "series14-week01-group-a.html",
                        self.group_a_html,
                    )
                ],
            )

            destination = (
                Path(root)
                / "Series_14"
                / "Week_01"
                / "Group_A"
            )

            self.assertTrue(
                Path(root, BATCH_FILENAME).is_file()
            )
            self.assertTrue(
                Path(
                    destination,
                    ".modus_capture_session.json",
                ).is_file()
            )
            self.assertTrue(
                Path(destination, "results.html").is_file()
            )

        self.assertEqual(batch.total_groups, 1)
        self.assertEqual(batch.completed_groups, 0)
        self.assertEqual(batch.remaining_groups, 1)

        item = batch.items[0]

        self.assertEqual(item.series_id, 14)
        self.assertEqual(item.week_id, 165)
        self.assertEqual(item.week_label, "Week 1")
        self.assertEqual(item.group, "Group A")
        self.assertEqual(
            item.destination_folder.name,
            "Group_A",
        )
        self.assertEqual(
            item.destination_folder.parent.name,
            "Week_01",
        )
        self.assertIsNotNone(batch.next_item)

    def test_load_refreshes_capture_progress(self):
        with tempfile.TemporaryDirectory() as root:
            batch = self.service.create(
                root=root,
                results_pages=[
                    ("group-a.html", self.group_a_html)
                ],
            )

            item = batch.items[0]
            session_path = (
                item.destination_folder
                / ".modus_capture_session.json"
            )

            payload = json.loads(
                session_path.read_text(encoding="utf-8")
            )
            first = payload["items"][0]

            Path(
                item.destination_folder,
                first["destination_filename"],
            ).write_text(
                "<html>captured match</html>",
                encoding="utf-8",
            )

            refreshed = self.service.load(root)

        self.assertEqual(refreshed.captured_matches, 1)
        self.assertEqual(
            refreshed.items[0].captured_count,
            1,
        )

    def test_reuses_existing_capture_session(self):
        with tempfile.TemporaryDirectory() as root:
            first = self.service.create(
                root=root,
                results_pages=[
                    ("group-a.html", self.group_a_html)
                ],
            )

            second = self.service.create(
                root=root,
                results_pages=[
                    ("group-a-copy.html", self.group_a_html)
                ],
            )

        self.assertEqual(
            first.items[0].destination_folder,
            second.items[0].destination_folder,
        )
        self.assertEqual(second.total_groups, 1)

    def test_rejects_duplicate_group_in_same_batch(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(
                ValueError,
                "Duplicate capture group",
            ):
                self.service.create(
                    root=root,
                    results_pages=[
                        ("first.html", self.group_a_html),
                        ("second.html", self.group_a_html),
                    ],
                )

    def test_clear_removes_only_batch_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            batch = self.service.create(
                root=root,
                results_pages=[
                    ("group-a.html", self.group_a_html)
                ],
            )

            self.assertTrue(self.service.clear(root))
            self.assertFalse(
                Path(root, BATCH_FILENAME).exists()
            )
            self.assertTrue(
                Path(
                    batch.items[0].destination_folder,
                    ".modus_capture_session.json",
                ).exists()
            )

    def test_week_folder_uses_display_label(self):
        self.assertEqual(
            self.service._week_folder("Week 1"),
            "Week_01",
        )
        self.assertEqual(
            self.service._week_folder("Week 13"),
            "Week_13",
        )

    def test_week_folder_rejects_invalid_label(self):
        with self.assertRaisesRegex(
            ValueError,
            "Could not determine display week",
        ):
            self.service._week_folder("Unknown")


if __name__ == "__main__":
    unittest.main()
