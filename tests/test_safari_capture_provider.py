import tempfile
import unittest
from pathlib import Path

from app.services.capture_provider import CaptureRequest
from app.services.capture_writer import CaptureWriter
from app.services.safari_capture_provider import (
    SafariCaptureProvider,
)


class FakeBrowserSession:
    def __init__(
        self,
        *,
        html,
        title="MODUS Match",
        current_url=(
            "https://example.test/match/16954"
        ),
    ):
        self._html = html
        self._title = title
        self._current_url = current_url
        self.goto_calls = []
        self.wait_calls = []
        self.closed = False
        self.running = True

    def open(self):
        self.running = True

    def goto(self, url, *, timeout_seconds=30.0):
        self.goto_calls.append(
            (url, timeout_seconds)
        )

    def wait_for(
        self,
        predicate,
        *,
        timeout_seconds=30.0,
        description="browser condition",
    ):
        self.wait_calls.append(
            (timeout_seconds, description)
        )

        if not predicate():
            raise TimeoutError(description)

    def html(self):
        return self._html

    def title(self):
        return self._title

    def current_url(self):
        return self._current_url

    def close(self):
        self.closed = True
        self.running = False


class SafariCaptureProviderTests(unittest.TestCase):
    def make_request(self, folder):
        return CaptureRequest(
            match_id=16954,
            source_url=(
                "https://example.test/match/16954"
            ),
            destination_folder=Path(folder),
            destination_filename="match_16954.html",
            player_a_name="Conan Whitehead",
            player_b_name="Jack Smith",
        )

    def test_captures_matching_page_by_player_names(self):
        html = (
            "<html><body>"
            "Conan Whitehead vs Jack Smith"
            "</body></html>"
        )
        browser = FakeBrowserSession(html=html)
        provider = SafariCaptureProvider(
            browser_session=browser,
            timeout_seconds=5,
        )

        with tempfile.TemporaryDirectory() as folder:
            request = self.make_request(folder)
            result = provider.capture(request)

        self.assertTrue(result.successful)
        self.assertTrue(result.has_html)
        self.assertEqual(result.provider, "safari")
        self.assertEqual(result.match_id, 16954)
        self.assertEqual(
            browser.goto_calls,
            [
                (
                    "https://example.test/match/16954",
                    5,
                )
            ],
        )

    def test_capture_can_be_written_to_destination(self):
        html = (
            "<html><body>"
            "Match 16954 Conan Whitehead Jack Smith"
            "</body></html>"
        )
        browser = FakeBrowserSession(html=html)
        provider = SafariCaptureProvider(
            browser_session=browser,
        )

        with tempfile.TemporaryDirectory() as folder:
            request = self.make_request(folder)
            result = provider.capture(request)
            written = CaptureWriter().write(
                request,
                result,
            )

            saved = request.destination_path.read_text(
                encoding="utf-8"
            )

        self.assertTrue(written.successful)
        self.assertIn("Conan Whitehead", saved)

    def test_rejects_wrong_match_page(self):
        browser = FakeBrowserSession(
            html=(
                "<html><body>"
                "Different Player vs Another Player"
                "</body></html>"
            )
        )
        provider = SafariCaptureProvider(
            browser_session=browser,
        )

        with tempfile.TemporaryDirectory() as folder:
            result = provider.capture(
                self.make_request(folder)
            )

        self.assertTrue(result.failed)
        self.assertIn(
            "MODUS match 16954 content",
            result.error,
        )

    def test_rejects_access_challenge(self):
        browser = FakeBrowserSession(
            html=(
                "<html><body>"
                "16954 Conan Whitehead Jack Smith "
                "Verify you are human"
                "</body></html>"
            )
        )
        provider = SafariCaptureProvider(
            browser_session=browser,
        )

        with tempfile.TemporaryDirectory() as folder:
            result = provider.capture(
                self.make_request(folder)
            )

        self.assertTrue(result.failed)
        self.assertIn(
            "access challenge",
            result.error,
        )

    def test_close_closes_browser_session(self):
        browser = FakeBrowserSession(
            html="<html>16954</html>"
        )
        provider = SafariCaptureProvider(
            browser_session=browser,
        )

        provider.close()

        self.assertTrue(browser.closed)


if __name__ == "__main__":
    unittest.main()
