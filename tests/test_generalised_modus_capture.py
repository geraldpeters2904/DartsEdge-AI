import json
import tempfile
import unittest
from pathlib import Path

from app.services.capture_wizard_service import CaptureWizardService
from app.services.modus_capture_session_service import (
    ModusCaptureSessionService,
    SESSION_FILENAME,
)


WEEK_1 = Path(
    "tests/fixtures/modus_capture/series14_week01_group_a.html"
)
WEEK_13 = Path(
    "tests/fixtures/modus/results_series14_week13_group_a_real.html"
)


class GeneralisedModusCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.week_1_html = WEEK_1.read_text(encoding="utf-8")
        cls.week_13_html = WEEK_13.read_text(encoding="utf-8")

    def setUp(self):
        self.service = ModusCaptureSessionService()

    def test_series_14_week_13_group_a_is_supported(self):
        with tempfile.TemporaryDirectory() as folder:
            session = self.service.create_session(
                results_filename="week13-group-a.html",
                results_html=self.week_13_html,
                destination_folder=folder,
            )

        self.assertEqual(session.series_id, 14)
        self.assertEqual(session.week_id, 177)
        self.assertEqual(session.week_label, "Week 13")
        self.assertEqual(session.group, "Group A")
        self.assertEqual(session.expected_count, 45)
        self.assertEqual(session.items[0].match_id, 18195)

    def test_group_b_is_supported(self):
        group_b = self.week_13_html.replace(
            "changeGroup('Group A')",
            "changeGroup('Group B')",
            1,
        )

        with tempfile.TemporaryDirectory() as folder:
            session = self.service.create_session(
                results_filename="week13-group-b.html",
                results_html=group_b,
                destination_folder=folder,
            )

        self.assertEqual(session.group, "Group B")
        self.assertEqual(session.expected_count, 45)

    def test_group_c_is_supported(self):
        group_c = self.week_13_html.replace(
            "changeGroup('Group A')",
            "changeGroup('Group C')",
            1,
        )

        with tempfile.TemporaryDirectory() as folder:
            session = self.service.create_session(
                results_filename="week13-group-c.html",
                results_html=group_c,
                destination_folder=folder,
            )

        self.assertEqual(session.group, "Group C")

    def test_final_is_supported(self):
        final_html = self.week_13_html.replace(
            "changeGroup('Group A')",
            "changeGroup('Final')",
            1,
        )

        with tempfile.TemporaryDirectory() as folder:
            session = self.service.create_session(
                results_filename="week13-final.html",
                results_html=final_html,
                destination_folder=folder,
            )

        self.assertEqual(session.group, "Final")

    def test_capture_wizard_creates_week_13_folder(self):
        wizard = CaptureWizardService()

        with tempfile.TemporaryDirectory() as root:
            result = wizard.create_from_pages(
                capture_root=root,
                saved_pages=[
                    ("series14-week13-group-a.html", self.week_13_html)
                ],
            )

        self.assertEqual(result.created_count, 1)
        created = result.created[0]
        self.assertEqual(created.week_label, "Week 13")
        self.assertTrue(
            str(created.destination_folder).endswith(
                "Series_14/Week_13/Group_A"
            )
        )

    def test_existing_match_pages_are_preserved_on_rebuild(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "match_18195.html").write_text(
                "<html></html>",
                encoding="utf-8",
            )

            session = self.service.create_session(
                results_filename="week13-group-a.html",
                results_html=self.week_13_html,
                destination_folder=folder,
            )

            self.assertEqual(session.captured_count, 1)
            self.assertEqual(session.next_item.match_id, 18196)

    def test_session_json_records_actual_page_context(self):
        with tempfile.TemporaryDirectory() as folder:
            self.service.create_session(
                results_filename="week13-group-a.html",
                results_html=self.week_13_html,
                destination_folder=folder,
            )
            payload = json.loads(
                Path(folder, SESSION_FILENAME).read_text(encoding="utf-8")
            )

        self.assertEqual(payload["series_label"], "Series 14")
        self.assertEqual(payload["week_label"], "Week 13")
        self.assertEqual(payload["group"], "Group A")


if __name__ == "__main__":
    unittest.main()
