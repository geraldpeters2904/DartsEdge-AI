import json
import tempfile
import unittest
from pathlib import Path

from app.services.modus_capture_assistant_service import (
    ModusCaptureAssistantService,
)


class ModusCaptureAssistantTests(unittest.TestCase):
    def setUp(self):
        self.service = ModusCaptureAssistantService()

    def create_session(self, destination):
        payload = {
            "items": [
                {
                    "match_id": 16952,
                    "filename": "match_16952.html",
                    "player_a": "Conan Whitehead",
                    "player_b": "Jack Smith",
                }
            ]
        }
        Path(
            destination,
            ".modus_capture_session.json",
        ).write_text(json.dumps(payload), encoding="utf-8")

    def test_start_requires_session_file(self):
        with tempfile.TemporaryDirectory() as destination:
            with tempfile.TemporaryDirectory() as watch:
                with self.assertRaisesRegex(ValueError, "session JSON"):
                    self.service.start(destination, watch)

    def test_expected_item_comes_from_session(self):
        with tempfile.TemporaryDirectory() as destination:
            self.create_session(destination)
            expected = self.service._expected_item(Path(destination))

        self.assertEqual(expected["match_id"], 16952)
        self.assertEqual(expected["filename"], "match_16952.html")

    def test_accepts_matching_saved_page(self):
        with tempfile.TemporaryDirectory() as destination:
            with tempfile.TemporaryDirectory() as watch:
                self.create_session(destination)
                self.service.start(destination, watch)

                saved = Path(watch, "Super Series Match.html")
                saved.write_text(
                    "<html>match/16952 Conan Whitehead Jack Smith</html>",
                    encoding="utf-8",
                )
                self.service.process_once()

                self.assertTrue(
                    Path(destination, "match_16952.html").is_file()
                )
                self.assertEqual(self.service.status().accepted_count, 1)
                self.service.stop()

    def test_rejects_wrong_match_page(self):
        with tempfile.TemporaryDirectory() as destination:
            with tempfile.TemporaryDirectory() as watch:
                self.create_session(destination)
                self.service.start(destination, watch)

                saved = Path(watch, "wrong.html")
                saved.write_text(
                    "<html>match/99999 Other Player Another Player</html>",
                    encoding="utf-8",
                )
                self.service.process_once()

                self.assertTrue(saved.is_file())
                self.assertEqual(self.service.status().rejected_count, 1)
                self.service.stop()


if __name__ == "__main__":
    unittest.main()
