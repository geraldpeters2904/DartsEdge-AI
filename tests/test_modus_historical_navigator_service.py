import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.modus_historical_catalog_service import (
    ModusHistoricalCaptureTarget,
)
from app.services.modus_historical_navigator_service import (
    ModusHistoricalNavigatorService,
)


TARGET = ModusHistoricalCaptureTarget(
    series_id=14,
    series_label="Series 14",
    week_id=165,
    week_label="Week 1",
    group="Group A",
    source_url=(
        "https://modussuperseries.com/results?"
        "series_id=14&week_id=165&group=Group+A"
    ),
)


class FakeBrowserSession:
    def __init__(self):
        self.goto_calls = []
        self.wait_calls = []
        self.closed = False
        self.page_html = "<html>results</html>"

    @property
    def running(self):
        return True

    def open(self):
        pass

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
        return self.page_html

    def title(self):
        return "MODUS Results"

    def current_url(self):
        return TARGET.source_url

    def close(self):
        self.closed = True


class FakeCatalogService:
    def __init__(self):
        self.target = TARGET
        self.calls = []

    def selected_target(self, html_text):
        self.calls.append(html_text)
        return self.target


@dataclass
class FakeSession:
    expected_count: int = 45
    captured_count: int = 0
    missing_count: int = 45


class FakeCaptureSessionService:
    def __init__(self):
        self.calls = []
        self.session = FakeSession()

    def create_session(
        self,
        *,
        results_filename,
        results_html,
        destination_folder,
    ):
        destination = Path(destination_folder)
        destination.mkdir(
            parents=True,
            exist_ok=True,
        )
        (
            destination
            / ".modus_capture_session.json"
        ).write_text("{}", encoding="utf-8")

        self.calls.append(
            (
                results_filename,
                results_html,
                destination,
            )
        )
        return self.session


class ModusHistoricalNavigatorServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.browser = FakeBrowserSession()
        self.catalog = FakeCatalogService()
        self.capture = FakeCaptureSessionService()
        self.service = ModusHistoricalNavigatorService(
            browser_session=self.browser,
            catalog_service=self.catalog,
            capture_session_service=self.capture,
            timeout_seconds=5,
        )

    def test_prepares_target_capture_session(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.service.prepare_target(
                root=root,
                target=TARGET,
            )

        self.assertTrue(result.created)
        self.assertEqual(result.expected_matches, 45)
        self.assertEqual(result.missing_matches, 45)
        self.assertEqual(
            self.browser.goto_calls,
            [(TARGET.source_url, 5)],
        )
        self.assertEqual(
            result.destination_folder.name,
            "Group_A",
        )
        self.assertEqual(
            result.destination_folder.parent.name,
            "Week_01",
        )
        self.assertEqual(
            result.destination_folder.parent.parent.name,
            "Series_14",
        )

    def test_existing_session_is_reported_as_refreshed(self):
        with tempfile.TemporaryDirectory() as root:
            destination = (
                self.service.destination_folder(
                    root=root,
                    target=TARGET,
                )
            )
            destination.mkdir(
                parents=True,
                exist_ok=True,
            )
            (
                destination
                / ".modus_capture_session.json"
            ).write_text("{}", encoding="utf-8")

            result = self.service.prepare_target(
                root=root,
                target=TARGET,
            )

        self.assertFalse(result.created)

    def test_wrong_loaded_scope_is_rejected(self):
        self.catalog.target = (
            ModusHistoricalCaptureTarget(
                series_id=14,
                series_label="Series 14",
                week_id=166,
                week_label="Week 2",
                group="Group A",
                source_url=TARGET.source_url,
            )
        )

        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(
                TimeoutError
            ):
                self.service.prepare_target(
                    root=root,
                    target=TARGET,
                )

        self.assertEqual(self.capture.calls, [])

    def test_final_uses_final_folder(self):
        final_target = (
            ModusHistoricalCaptureTarget(
                series_id=14,
                series_label="Series 14",
                week_id=165,
                week_label="Week 1",
                group="Final",
                source_url=(
                    "https://modussuperseries.com/results?"
                    "series_id=14&week_id=165&group=Final"
                ),
            )
        )

        folder = self.service.destination_folder(
            root="/tmp/history",
            target=final_target,
        )

        self.assertEqual(folder.name, "Final")

    def test_close_closes_browser(self):
        self.service.close()
        self.assertTrue(self.browser.closed)


if __name__ == "__main__":
    unittest.main()
