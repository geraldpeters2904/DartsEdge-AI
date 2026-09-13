import unittest
from datetime import date, datetime
from types import SimpleNamespace

from app.services.bookmaker_capture_service import (
    store_price_changes,
)
from app.services.bookmaker_capture_types import (
    CapturedBookmakerPrice,
)
from app.services.paddy_power_capture_service import (
    PaddyPowerCaptureService,
)
from app.services.paddy_power_modus_extractor import (
    normalise_name,
)


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return list(
            reversed(
                self.rows
            )
        )


class FakeDb:
    def __init__(self):
        self.rows = []
        self.commits = 0

    def query(self, model):
        return FakeQuery(
            self.rows
        )

    def add(self, row):
        row.id = (
            len(
                self.rows
            )
            + 1
        )
        self.rows.append(
            row
        )

    def commit(self):
        self.commits += 1


class FakeBrowser:
    def __init__(
        self,
        html,
        *,
        pages=None,
    ):
        self.page = html
        self.pages = list(
            pages or []
        )
        self.urls = []

    def goto(
        self,
        url,
        timeout_seconds,
    ):
        self.urls.append(
            url
        )

    def wait_for(
        self,
        predicate,
        timeout_seconds,
        description,
    ):
        if predicate():
            return

        for page in self.pages:
            self.page = page

            if predicate():
                return

        raise RuntimeError(
            description
        )

    def html(self):
        return self.page

    def close(self):
        pass


class FakeExtractor:
    def extract(
        self,
        html,
        *,
        captured_at,
    ):
        return [
            CapturedBookmakerPrice(
                fixture_date=date(
                    2026,
                    8,
                    7,
                ),
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                market=(
                    "match_winner"
                ),
                selection="Alpha",
                bookmaker=(
                    "Paddy Power"
                ),
                decimal_odds=1.90,
                captured_at=(
                    captured_at
                ),
                provider_id=(
                    "fake"
                ),
            )
        ]


class BookmakerCaptureTests(
    unittest.TestCase
):

    def test_player_name_apostrophe_variants_normalise_equally(
        self,
    ):
        expected = "john oshea"

        samples = (
            "John O´Shea",
            "John O'Shea",
            "John O’Shea",
            "John OShea",
        )

        for value in samples:
            self.assertEqual(
                normalise_name(value),
                expected,
            )
    def test_only_stores_price_change(self):
        db = FakeDb()

        price = (
            CapturedBookmakerPrice(
                fixture_date=date(
                    2026,
                    8,
                    7,
                ),
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                market="match_winner",
                selection="Alpha",
                bookmaker="Paddy Power",
                decimal_odds=1.90,
                captured_at=datetime(
                    2026,
                    8,
                    7,
                    10,
                    0,
                ),
                provider_id="test",
            )
        )

        first = (
            store_price_changes(
                db,
                [price],
            )
        )

        second = (
            store_price_changes(
                db,
                [price],
            )
        )

        self.assertEqual(
            first["stored"],
            1,
        )

        self.assertEqual(
            second["unchanged"],
            1,
        )

        self.assertEqual(
            len(
                db.rows
            ),
            1,
        )

    def test_capture_stores_extracted_price(self):
        db = FakeDb()

        service = (
            PaddyPowerCaptureService(
                browser_session=(
                    FakeBrowser(
                        "<html>MODUS</html>"
                    )
                )
            )
        )

        report = service.capture(
            db,
            source_url=(
                "https://example.test/darts"
            ),
            extractor=(
                FakeExtractor()
            ),
        )

        self.assertEqual(
            report.stored_prices,
            1,
        )

        self.assertFalse(
            report.challenge_detected
        )

    def test_capture_waits_for_custom_page_ready_condition(self):
        db = FakeDb()

        browser = FakeBrowser(
            "<html>Sports Login Sign Up</html>",
            pages=[
                "<html>Sports Darts</html>",
                (
                    "<html>"
                    "MODUS Super Series "
                    "Justin Smith "
                    "Danny Goddard"
                    "</html>"
                ),
            ],
        )

        service = PaddyPowerCaptureService(
            browser_session=browser
        )

        report = service.capture(
            db,
            source_url=(
                "https://example.test/darts"
            ),
            extractor=FakeExtractor(),
            page_ready=lambda html: (
                "MODUS Super Series"
                in html
            ),
        )

        self.assertEqual(
            report.stored_prices,
            1,
        )

    def test_capture_can_reject_page_before_extracting_prices(self):
        db = FakeDb()
        service = PaddyPowerCaptureService(
            browser_session=FakeBrowser(
                "<html>IN_PLAY event-card--item</html>"
            )
        )

        report = service.capture(
            db,
            source_url=(
                "https:" + "//example.test/darts"
            ),
            extractor=FakeExtractor(),
            page_allowed=lambda html: (
                "IN_PLAY" not in html
            ),
        )

        self.assertEqual(
            report.extracted_prices,
            0,
        )
        self.assertEqual(
            report.stored_prices,
            0,
        )
        self.assertEqual(
            len(db.rows),
            0,
        )
        self.assertIn(
            "rejected",
            report.message.casefold(),
        )

    def test_challenge_stops_capture(self):
        db = FakeDb()

        service = (
            PaddyPowerCaptureService(
                browser_session=(
                    FakeBrowser(
                        "<html>Verify you are human</html>"
                    )
                )
            )
        )

        report = service.capture(
            db,
            source_url=(
                "https://example.test/darts"
            ),
            extractor=(
                FakeExtractor()
            ),
        )

        self.assertTrue(
            report.challenge_detected
        )

        self.assertEqual(
            report.stored_prices,
            0,
        )

        self.assertEqual(
            len(
                db.rows
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
