import tempfile
import unittest
from pathlib import Path

from app.services.capture_provider import (
    CaptureRequest,
    CaptureResult,
)
from app.services.capture_provider_registry import (
    CaptureProviderRegistry,
)
from app.services.capture_writer import CaptureWriter
from app.services.manual_capture_provider import (
    ManualCaptureProvider,
)


class FakeCaptureProvider:
    name = "fake"

    def capture(self, request):
        return CaptureResult(
            provider=self.name,
            status="captured",
            match_id=request.match_id,
            destination_path=None,
            message="Fake capture completed.",
            html="<html><body>Fake match page</body></html>",
            source_url=request.source_url,
            page_title="Fake match",
        )


class CaptureProviderTests(unittest.TestCase):
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

    def test_manual_provider_waits_when_file_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            request = self.make_request(folder)

            result = ManualCaptureProvider().capture(
                request
            )

        self.assertTrue(result.waiting)
        self.assertFalse(result.successful)
        self.assertFalse(result.has_html)
        self.assertEqual(result.provider, "manual")
        self.assertEqual(result.match_id, 16954)
        self.assertIsNone(result.destination_path)

    def test_manual_provider_reports_existing_capture(self):
        with tempfile.TemporaryDirectory() as folder:
            request = self.make_request(folder)

            request.destination_path.write_text(
                "<html>captured</html>",
                encoding="utf-8",
            )

            result = ManualCaptureProvider().capture(
                request
            )

        self.assertTrue(result.successful)
        self.assertFalse(result.has_html)
        self.assertEqual(
            result.destination_path.name,
            "match_16954.html",
        )

    def test_registry_contains_manual_provider(self):
        registry = CaptureProviderRegistry()

        self.assertIn("manual", registry.names())
        self.assertIsInstance(
            registry.get("manual"),
            ManualCaptureProvider,
        )

    def test_registry_allows_provider_registration(self):
        registry = CaptureProviderRegistry()
        registry.register(FakeCaptureProvider())

        self.assertIn("fake", registry.names())
        self.assertIsInstance(
            registry.get("fake"),
            FakeCaptureProvider,
        )

    def test_registry_contains_safari_provider(self):
        registry = CaptureProviderRegistry()

        self.assertIn("safari", registry.names())
        self.assertEqual(
            registry.get("safari").name,
            "safari",
        )

    def test_registry_rejects_unknown_provider(self):
        registry = CaptureProviderRegistry()

        with self.assertRaisesRegex(
            ValueError,
            "Unknown capture provider",
        ):
            registry.get("unknown-provider")

    def test_writer_saves_provider_html(self):
        with tempfile.TemporaryDirectory() as folder:
            request = self.make_request(folder)
            provider = FakeCaptureProvider()

            result = provider.capture(request)
            written = CaptureWriter().write(
                request,
                result,
            )

            saved_html = (
                request.destination_path
                .read_text(encoding="utf-8")
            )

        self.assertTrue(written.successful)
        self.assertEqual(
            written.destination_path.name,
            "match_16954.html",
        )
        self.assertIn("Fake match page", saved_html)
        self.assertEqual(
            written.bytes_written,
            len(saved_html.encode("utf-8")),
        )

    def test_writer_rejects_missing_html(self):
        with tempfile.TemporaryDirectory() as folder:
            request = self.make_request(folder)

            result = CaptureResult(
                provider="fake",
                status="captured",
                match_id=16954,
                destination_path=None,
                message="No content.",
            )

            with self.assertRaisesRegex(
                ValueError,
                "returned no HTML",
            ):
                CaptureWriter().write(
                    request,
                    result,
                )

    def test_writer_rejects_wrong_match_id(self):
        with tempfile.TemporaryDirectory() as folder:
            request = self.make_request(folder)

            result = CaptureResult(
                provider="fake",
                status="captured",
                match_id=99999,
                destination_path=None,
                message="Wrong match.",
                html="<html>wrong match</html>",
            )

            with self.assertRaisesRegex(
                ValueError,
                "match ID does not match",
            ):
                CaptureWriter().write(
                    request,
                    result,
                )

    def test_writer_rejects_invalid_filename(self):
        with tempfile.TemporaryDirectory() as folder:
            request = CaptureRequest(
                match_id=16954,
                source_url="https://example.test",
                destination_folder=Path(folder),
                destination_filename="wrong-name.html",
                player_a_name="Player A",
                player_b_name="Player B",
            )

            result = FakeCaptureProvider().capture(
                request
            )

            with self.assertRaisesRegex(
                ValueError,
                "Expected 'match_16954.html'",
            ):
                CaptureWriter().write(
                    request,
                    result,
                )


if __name__ == "__main__":
    unittest.main()
