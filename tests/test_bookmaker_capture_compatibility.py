import unittest
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.models.odds_movement import OddsMovement
from app.models.odds_snapshot import OddsSnapshot
from app.services.bookmaker_capture_service import (
    store_price_changes,
)
from app.services.bookmaker_capture_types import (
    CapturedBookmakerPrice,
)


class BookmakerCaptureCompatibilityTests(
    unittest.TestCase
):
    def setUp(self):
        engine = create_engine(
            "sqlite:///:memory:"
        )
        Base.metadata.create_all(
            bind=engine
        )

        Session = sessionmaker(
            bind=engine
        )
        self.db = Session()

        self.match = Match(
            date=date(
                2026,
                8,
                8,
            ),
            tournament="MODUS",
            player_a="Alpha Player",
            player_b="Bravo Player",
            status="scheduled",
        )
        self.db.add(
            self.match
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def price(
        self,
        odds,
    ):
        return CapturedBookmakerPrice(
            fixture_date=date(
                2026,
                8,
                8,
            ),
            tournament="MODUS",
            player_a="Alpha Player",
            player_b="Bravo Player",
            market="match_winner",
            selection="Alpha Player",
            bookmaker="Paddy Power",
            decimal_odds=odds,
            captured_at=datetime(
                2026,
                8,
                8,
                10,
                0,
            ),
            provider_id="pp-test",
        )

    def test_existing_capture_writes_new_odds_schema(
        self,
    ):
        result = store_price_changes(
            self.db,
            [
                self.price(
                    2.10
                )
            ],
        )

        self.assertEqual(
            result["stored"],
            1,
        )

        row = (
            self.db.query(
                OddsSnapshot
            )
            .one()
        )

        self.assertEqual(
            row.fixture_id,
            self.match.id,
        )

        self.assertEqual(
            row.bookmaker_code,
            "paddypower",
        )

        self.assertEqual(
            row.source_reference,
            "pp-test",
        )

    def test_second_price_creates_movement(
        self,
    ):
        store_price_changes(
            self.db,
            [
                self.price(
                    2.10
                )
            ],
        )

        second = self.price(
            2.00
        )

        second = CapturedBookmakerPrice(
            fixture_date=second.fixture_date,
            tournament=second.tournament,
            player_a=second.player_a,
            player_b=second.player_b,
            market=second.market,
            selection=second.selection,
            bookmaker=second.bookmaker,
            decimal_odds=second.decimal_odds,
            captured_at=datetime(
                2026,
                8,
                8,
                10,
                5,
            ),
            provider_id=second.provider_id,
        )

        result = store_price_changes(
            self.db,
            [
                second
            ],
        )

        self.assertEqual(
            result["stored"],
            1,
        )

        self.assertEqual(
            result["movements"],
            1,
        )

        self.assertEqual(
            self.db.query(
                OddsMovement
            ).count(),
            1,
        )

    def test_reversed_player_order_resolves_fixture(
        self,
    ):
        price = self.price(
            1.95
        )

        reversed_price = (
            CapturedBookmakerPrice(
                fixture_date=price.fixture_date,
                tournament=price.tournament,
                player_a=price.player_b,
                player_b=price.player_a,
                market=price.market,
                selection=price.selection,
                bookmaker=price.bookmaker,
                decimal_odds=price.decimal_odds,
                captured_at=price.captured_at,
                provider_id=price.provider_id,
            )
        )

        result = store_price_changes(
            self.db,
            [
                reversed_price
            ],
        )

        self.assertEqual(
            result["stored"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
