import tempfile
import unittest
from pathlib import Path

from app.services.capture_provider import (
    CaptureRequest,
    CaptureResult,
)
from app.services.capture_validation_service import (
    CaptureValidationService,
)


class CaptureValidationServiceTests(unittest.TestCase):
    def setUp(self):
        self.validator = CaptureValidationService()

    def make_request(self, folder):
        return CaptureRequest(
            match_id=16954,
            source_url="https://example.test/match/16954",
            destination_folder=Path(folder),
            destination_filename="match_16954.html",
            player_a_name="Player A",
            player_b_name="Player B",
        )

    def make_result(self, html):
        return CaptureResult(
            provider="fake",
            status="captured",
            match_id=16954,
            destination_path=None,
            message="Captured.",
            html=html,
            source_url="https://example.test/match/16954",
        )

    def test_accepts_expected_match_page(self):
        with tempfile.TemporaryDirectory() as folder:
            validation = self.validator.validate(
                self.make_request(folder),
                self.make_result(
                    "<html>16954 Player A Player B</html>"
                ),
            )

        self.assertTrue(validation.valid)
        self.assertFalse(validation.retryable)

    def test_access_challenge_is_retryable(self):
        with tempfile.TemporaryDirectory() as folder:
            validation = self.validator.validate(
                self.make_request(folder),
                self.make_result(
                    "<html>16954 Verify you are human</html>"
                ),
            )

        self.assertFalse(validation.valid)
        self.assertTrue(validation.retryable)
        self.assertEqual(
            validation.marker,
            "verify you are human",
        )

    def test_wrong_match_is_not_retryable(self):
        with tempfile.TemporaryDirectory() as folder:
            validation = self.validator.validate(
                self.make_request(folder),
                self.make_result(
                    "<html>Unrelated match page</html>"
                ),
            )

        self.assertFalse(validation.valid)
        self.assertFalse(validation.retryable)


if __name__ == "__main__":
    unittest.main()
