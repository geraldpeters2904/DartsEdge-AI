import unittest
from datetime import date, datetime

from app.services.bookmaker_capture_service import (
    store_price_changes,
)
from app.services.bookmaker_capture_types import (
    CapturedBookmakerPrice,
)


class MinimalFakeDb:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1


class BookmakerCaptureFakeDbCompatibilityTests(
    unittest.TestCase
):
    def price(self, odds):
        return CapturedBookmakerPrice(
            fixture_date=date(
                2026,
                8,
                8,
            ),
            tournament="MODUS",
            player_a="Alpha",
            player_b="Bravo",
            market="match_winner",
            selection="Alpha",
            bookmaker="Paddy Power",
            decimal_odds=odds,
            captured_at=datetime(
                2026,
                8,
                8,
                10,
                0,
            ),
            provider_id="test",
        )

    def test_fake_db_keeps_legacy_unit_contract(
        self,
    ):
        db = MinimalFakeDb()

        first = store_price_changes(
            db,
            [
                self.price(
                    1.90
                )
            ],
        )

        second = store_price_changes(
            db,
            [
                self.price(
                    1.90
                )
            ],
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
                db.added
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
