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
    ):
        self.page = html
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
        if not predicate():
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
