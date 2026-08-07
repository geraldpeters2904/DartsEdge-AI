import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.modus_fixture_discovery_service import (
    ModusFixtureDiscoveryService,
)


UPCOMING_HTML = Path(
    "tests/fixtures/modus_fixture_lifecycle/upcoming.html"
).read_text(encoding="utf-8")


class FakeBrowserSession:
    def __init__(self, html=UPCOMING_HTML):
        self.page_html = html
        self.goto_calls = []
        self.wait_calls = []
        self.closed = False

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
        return "MODUS Fixtures"

    def current_url(self):
        return (
            "https://modussuperseries.com/results?"
            "series_id=15&week_id=178&group=Group+A"
        )

    def close(self):
        self.closed = True


@dataclass
class FakeImportResult:
    fixture_count: int = 3


class FakeFixtureImporter:
    def __init__(self):
        self.calls = []

    def import_html(
        self,
        db,
        *,
        html_text,
        source_name,
    ):
        self.calls.append(
            (db, html_text, source_name)
        )
        return FakeImportResult()


class ModusFixtureDiscoveryServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.browser = FakeBrowserSession()
        self.importer = FakeFixtureImporter()
        self.service = ModusFixtureDiscoveryService(
            browser_session=self.browser,
            fixture_import_service=self.importer,
            timeout_seconds=5,
        )

    def test_discovers_and_imports_fixture_page(self):
        db = object()

        result = self.service.discover(
            db,
            series_id=15,
            week_id=178,
            group="Group A",
        )

        self.assertTrue(result.imported)
        self.assertTrue(result.changed)
        self.assertEqual(
            result.import_result.fixture_count,
            3,
        )
        self.assertEqual(len(self.importer.calls), 1)
        self.assertEqual(
            self.browser.goto_calls[0][0],
            (
                "https://modussuperseries.com/results?"
                "series_id=15&week_id=178&group=Group+A"
            ),
        )

    def test_unchanged_page_is_not_reimported(self):
        db = object()

        first = self.service.discover(
            db,
            series_id=15,
            week_id=178,
            group="Group A",
        )
        second = self.service.discover(
            db,
            series_id=15,
            week_id=178,
            group="Group A",
        )

        self.assertTrue(first.imported)
        self.assertTrue(second.unchanged)
        self.assertFalse(second.changed)
        self.assertEqual(len(self.importer.calls), 1)

    def test_changed_html_is_imported_again(self):
        db = object()

        self.service.discover(
            db,
            series_id=15,
            week_id=178,
            group="Group A",
        )

        self.browser.page_html = (
            UPCOMING_HTML + "<!-- changed -->"
        )

        second = self.service.discover(
            db,
            series_id=15,
            week_id=178,
            group="Group A",
        )

        self.assertTrue(second.imported)
        self.assertEqual(len(self.importer.calls), 2)

    def test_close_closes_browser(self):
        self.service.close()
        self.assertTrue(self.browser.closed)

    def test_invalid_group_is_rejected_before_browser(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported MODUS group",
        ):
            self.service.discover(
                object(),
                series_id=15,
                week_id=178,
                group="Unknown",
            )

        self.assertEqual(self.browser.goto_calls, [])


if __name__ == "__main__":
    unittest.main()
