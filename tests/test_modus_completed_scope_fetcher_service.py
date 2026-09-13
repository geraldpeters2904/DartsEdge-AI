from __future__ import annotations

import unittest

from app.services.modus_import_scope_service import ModusImportScope
from app.services.modus_completed_scope_fetcher_service import (
    ModusCompletedScopeFetcherService,
)


class FakeBrowser:
    def __init__(self, html):
        self._html = html
        self.urls = []
        self.closed = False

    def goto(self, url):
        self.urls.append(url)

    def wait_until(self, predicate, timeout_seconds=0):
        return True

    def html(self):
        return self._html

    def close(self):
        self.closed = True


class FakeLifecycle:
    def __init__(self, cards):
        self.cards = tuple(cards)
        self.html_seen = None

    def parse_cards(self, html):
        self.html_seen = html
        return self.cards


class Card:
    def __init__(self, match_id, status):
        self.match_id = match_id
        self.status = status


class ModusCompletedScopeFetcherTests(unittest.TestCase):

    def test_fetches_exact_scope_and_returns_completed_only(self):
        completed = Card(1001, "completed")
        scheduled = Card(1002, "scheduled")

        browser = FakeBrowser("<html>results</html>")
        lifecycle = FakeLifecycle(
            (scheduled, completed)
        )

        service = ModusCompletedScopeFetcherService(
            browser=browser,
            lifecycle_service=lifecycle,
        )

        scope = ModusImportScope(
            series_id=26,
            week_id=196,
            group="Group A",
        )

        cards = service.fetch(scope)

        self.assertEqual(cards, (completed,))
        self.assertEqual(
            browser.urls,
            [
                "https://modussuperseries.com/results"
                "?series_id=26&week_id=196&group=Group+A"
            ],
        )
        self.assertEqual(
            lifecycle.html_seen,
            "<html>results</html>",
        )

    def test_close_closes_browser(self):
        browser = FakeBrowser("<html></html>")

        service = ModusCompletedScopeFetcherService(
            browser=browser,
            lifecycle_service=FakeLifecycle(()),
        )

        service.close()

        self.assertTrue(browser.closed)


if __name__ == "__main__":
    unittest.main()
