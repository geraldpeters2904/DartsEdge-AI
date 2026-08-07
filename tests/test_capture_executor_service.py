import tempfile
import unittest
from pathlib import Path

from app.services.capture_executor_service import (
    CaptureExecutorService,
)
from app.services.capture_provider import (
    CaptureRequest,
    CaptureResult,
)
from app.services.capture_provider_registry import (
    CaptureProviderRegistry,
)


class HtmlCaptureProvider:
    name = "html"

    def capture(self, request):
        return CaptureResult(
            provider=self.name,
            status="captured",
            match_id=request.match_id,
            destination_path=None,
            message="HTML captured.",
            html=(
                "<html><body>"
                "Match 16954 Player A Player B"
                "</body></html>"
            ),
            source_url=request.source_url,
        )


class WaitingCaptureProvider:
    name = "waiting"

    def capture(self, request):
        return CaptureResult(
            provider=self.name,
            status="waiting",
            match_id=request.match_id,
            destination_path=None,
            message="Waiting for capture.",
        )


class FailedCaptureProvider:
    name = "failed"

    def capture(self, request):
        return CaptureResult(
            provider=self.name,
            status="failed",
            match_id=request.match_id,
            destination_path=None,
            message="Capture failed.",
            error="Provider failure.",
        )


class ExistingCaptureProvider:
    name = "existing"

    def capture(self, request):
        return CaptureResult(
            provider=self.name,
            status="captured",
            match_id=request.match_id,
            destination_path=request.destination_path,
            message="Capture already exists.",
        )


class CaptureExecutorServiceTests(unittest.TestCase):
    def make_request(self, folder):
        return CaptureRequest(
            match_id=16954,
            source_url=(
                "https://example.test/match/16954"
            ),
            destination_folder=Path(folder),
            destination_filename="match_16954.html",
            player_a_name="Player A",
            player_b_name="Player B",
        )

    def make_executor(self, provider):
        registry = CaptureProviderRegistry(
            include_safari=False,
        )
        registry.register(provider)

        return CaptureExecutorService(
            provider_registry=registry,
        )

    def test_execute_writes_provider_html(self):
        with tempfile.TemporaryDirectory() as folder:
            request = self.make_request(folder)
            executor = self.make_executor(
                HtmlCaptureProvider()
            )

            result = executor.execute(
                request,
                provider_name="html",
            )

            saved_html = request.destination_path.read_text(
                encoding="utf-8",
            )

        self.assertTrue(result.successful)
        self.assertEqual(
            result.destination_path,
            request.destination_path,
        )
        self.assertIn("Match 16954", saved_html)
        self.assertIn("Player A", saved_html)
        self.assertIn("Player B", saved_html)
        self.assertEqual(
            result.bytes_written,
            len(saved_html.encode("utf-8")),
        )

    def test_execute_returns_waiting_result(self):
        with tempfile.TemporaryDirectory() as folder:
            request = self.make_request(folder)
            executor = self.make_executor(
                WaitingCaptureProvider()
            )

            result = executor.execute(
                request,
                provider_name="waiting",
            )

        self.assertTrue(result.waiting)
        self.assertFalse(request.destination_path.exists())

    def test_execute_returns_failed_result(self):
        with tempfile.TemporaryDirectory() as folder:
            request = self.make_request(folder)
            executor = self.make_executor(
                FailedCaptureProvider()
            )

            result = executor.execute(
                request,
                provider_name="failed",
            )

        self.assertTrue(result.failed)
        self.assertEqual(
            result.error,
            "Provider failure.",
        )
        self.assertFalse(request.destination_path.exists())

    def test_execute_returns_existing_capture(self):
        with tempfile.TemporaryDirectory() as folder:
            request = self.make_request(folder)
            request.destination_path.write_text(
                "<html>Existing capture</html>",
                encoding="utf-8",
            )
            executor = self.make_executor(
                ExistingCaptureProvider()
            )

            result = executor.execute(
                request,
                provider_name="existing",
            )

        self.assertTrue(result.successful)
        self.assertEqual(
            result.destination_path,
            request.destination_path,
        )
        self.assertIsNone(result.bytes_written)


    def test_execute_rejects_access_challenge_html(self):
        class ChallengeProvider:
            name = "challenge"

            def capture(self, request):
                return CaptureResult(
                    provider=self.name,
                    status="captured",
                    match_id=request.match_id,
                    destination_path=None,
                    message="HTML captured.",
                    html=(
                        "<html><body>"
                        "16954 Player A Player B "
                        "Verify you are human"
                        "</body></html>"
                    ),
                    source_url=request.source_url,
                )

        with tempfile.TemporaryDirectory() as folder:
            request = self.make_request(folder)
            executor = self.make_executor(
                ChallengeProvider()
            )

            result = executor.execute(
                request,
                provider_name="challenge",
            )

        self.assertTrue(result.failed)
        self.assertIn(
            "access challenge",
            result.error,
        )
        self.assertFalse(
            request.destination_path.exists()
        )

    def test_execute_rejects_wrong_match_html(self):
        class WrongMatchProvider:
            name = "wrong-match"

            def capture(self, request):
                return CaptureResult(
                    provider=self.name,
                    status="captured",
                    match_id=request.match_id,
                    destination_path=None,
                    message="HTML captured.",
                    html=(
                        "<html><body>"
                        "Different Player vs Another Player"
                        "</body></html>"
                    ),
                    source_url=request.source_url,
                )

        with tempfile.TemporaryDirectory() as folder:
            request = self.make_request(folder)
            executor = self.make_executor(
                WrongMatchProvider()
            )

            result = executor.execute(
                request,
                provider_name="wrong-match",
            )

        self.assertTrue(result.failed)
        self.assertIn(
            "does not match expected match",
            result.error,
        )
        self.assertFalse(
            request.destination_path.exists()
        )

    def test_execute_rejects_login_page(self):
        class LoginProvider:
            name = "login"

            def capture(self, request):
                return CaptureResult(
                    provider=self.name,
                    status="captured",
                    match_id=request.match_id,
                    destination_path=None,
                    message="HTML captured.",
                    html=(
                        "<html><body>"
                        "16954 Player A Player B "
                        "Sign in to continue"
                        "</body></html>"
                    ),
                    source_url=request.source_url,
                )

        with tempfile.TemporaryDirectory() as folder:
            request = self.make_request(folder)
            executor = self.make_executor(
                LoginProvider()
            )

            result = executor.execute(
                request,
                provider_name="login",
            )

        self.assertTrue(result.failed)
        self.assertIn(
            "requires authentication",
            result.error,
        )
        self.assertFalse(
            request.destination_path.exists()
        )


if __name__ == "__main__":
    unittest.main()
