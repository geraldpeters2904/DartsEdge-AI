import tempfile
import unittest
from pathlib import Path

from app.services.modus_capture_session_service import (
    ModusCaptureSessionService,
)


class RelaxedCaptureIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.service = ModusCaptureSessionService()

    def test_minimal_html_counts_as_captured(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "match_1.html"
            path.write_text(
                "<html></html>",
                encoding="utf-8",
            )

            self.assertTrue(
                self.service._captured_page_is_valid(
                    path,
                    1,
                )
            )

    def test_safari_error_page_does_not_count_as_captured(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "match_16347.html"
            path.write_text(
                (
                    "<p>Safari can’t open the page because "
                    "the server where this page is located "
                    "isn’t responding.</p>"
                ),
                encoding="utf-8",
            )

            self.assertFalse(
                self.service._captured_page_is_valid(
                    path,
                    16347,
                )
            )


if __name__ == "__main__":
    unittest.main()
