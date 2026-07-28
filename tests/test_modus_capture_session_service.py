import json
import tempfile
import unittest
from pathlib import Path

from app.services.modus_capture_session_service import (
    ModusCaptureSessionService,
    SESSION_FILENAME,
)


RESULTS_FIXTURE = Path(
    "tests/fixtures/modus_capture/series14_week01_group_a.html"
)


class ModusCaptureSessionServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results_html = RESULTS_FIXTURE.read_text(encoding="utf-8")

    def setUp(self):
        self.service = ModusCaptureSessionService()

    def test_builds_real_series_14_week_1_group_a_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            session = self.service.create_session(
                results_filename="series14_week01_group_a.html",
                results_html=self.results_html,
                destination_folder=folder,
            )

            self.assertEqual(session.series_id, 14)
            self.assertEqual(session.series_label, "Series 14")
            self.assertEqual(session.week_id, 165)
            self.assertEqual(session.week_label, "Week 1")
            self.assertEqual(session.group, "Group A")
            self.assertEqual(session.expected_count, 45)

    def test_queue_uses_real_first_and_last_match_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            session = self.service.create_session(
                results_filename="source.html",
                results_html=self.results_html,
                destination_folder=folder,
            )

            self.assertEqual(session.items[0].match_id, 16947)
            self.assertEqual(session.items[0].match_number, 1)
            self.assertEqual(session.items[-1].match_id, 16991)
            self.assertEqual(session.items[-1].match_number, 45)

    def test_queue_contains_players_scores_urls_and_filenames(self):
        with tempfile.TemporaryDirectory() as folder:
            session = self.service.create_session(
                results_filename="source.html",
                results_html=self.results_html,
                destination_folder=folder,
            )
            first = session.items[0]

            self.assertEqual(first.player_a_name, "Jeff Smith")
            self.assertEqual(first.player_b_name, "Dawson Murschell")
            self.assertEqual(first.player_a_legs, 1)
            self.assertEqual(first.player_b_legs, 4)
            self.assertEqual(first.destination_filename, "match_16947.html")
            self.assertTrue(first.source_url.endswith("match_id=16947"))

    def test_creates_results_and_session_files(self):
        with tempfile.TemporaryDirectory() as folder:
            self.service.create_session(
                results_filename="source.html",
                results_html=self.results_html,
                destination_folder=folder,
            )

            self.assertTrue(Path(folder, "results.html").exists())
            self.assertTrue(Path(folder, SESSION_FILENAME).exists())

    def test_new_session_starts_with_all_pages_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            session = self.service.create_session(
                results_filename="source.html",
                results_html=self.results_html,
                destination_folder=folder,
            )

            self.assertEqual(session.captured_count, 0)
            self.assertEqual(session.missing_count, 45)
            self.assertFalse(session.complete)
            self.assertEqual(session.next_item.match_id, 16947)

    def test_refresh_marks_existing_match_files_as_captured(self):
        with tempfile.TemporaryDirectory() as folder:
            self.service.create_session(
                results_filename="source.html",
                results_html=self.results_html,
                destination_folder=folder,
            )
            Path(folder, "match_16947.html").write_text(
                "<html></html>",
                encoding="utf-8",
            )

            refreshed = self.service.refresh_session(folder)

            self.assertEqual(refreshed.captured_count, 1)
            self.assertEqual(refreshed.missing_count, 44)
            self.assertEqual(refreshed.next_item.match_id, 16948)

    def test_resume_skips_multiple_existing_files(self):
        with tempfile.TemporaryDirectory() as folder:
            self.service.create_session(
                results_filename="source.html",
                results_html=self.results_html,
                destination_folder=folder,
            )
            for match_id in (16947, 16948, 16949):
                Path(folder, f"match_{match_id}.html").write_text(
                    "<html></html>",
                    encoding="utf-8",
                )

            refreshed = self.service.refresh_session(folder)

            self.assertEqual(refreshed.captured_count, 3)
            self.assertEqual(refreshed.next_item.match_id, 16950)

    def test_session_json_contains_progress_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            self.service.create_session(
                results_filename="source.html",
                results_html=self.results_html,
                destination_folder=folder,
            )

            payload = json.loads(
                Path(folder, SESSION_FILENAME).read_text(encoding="utf-8")
            )

            self.assertEqual(payload["expected_count"], 45)
            self.assertEqual(payload["captured_count"], 0)
            self.assertEqual(payload["missing_count"], 45)
            self.assertEqual(payload["next_match_id"], 16947)
            self.assertEqual(len(payload["items"]), 45)

    def test_missing_session_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(
                ValueError,
                "No MODUS capture session",
            ):
                self.service.refresh_session(folder)

    def test_blank_destination_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "destination folder"):
            self.service.create_session(
                results_filename="source.html",
                results_html=self.results_html,
                destination_folder="",
            )


if __name__ == "__main__":
    unittest.main()
