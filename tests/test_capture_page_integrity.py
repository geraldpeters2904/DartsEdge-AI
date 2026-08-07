import tempfile
import unittest
from pathlib import Path

from app.services.modus_capture_session_service import (
    ModusCaptureSessionService,
)


class CapturePageIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.service = ModusCaptureSessionService()

    def test_browser_error_page_is_not_captured(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "match_16347.html"
            path.write_text(
                "<p>Safari can’t open the page because the server isn’t responding.</p>",
                encoding="utf-8",
            )
            self.assertFalse(
                self.service._captured_page_is_valid(path, 16347)
            )

    def test_real_fixture_page_is_captured(self):
        path = Path("tests/fixtures/modus/match_18195_real.html")
        self.assertTrue(
            self.service._captured_page_is_valid(path, 18195)
        )


if __name__ == "__main__":
    unittest.main()
