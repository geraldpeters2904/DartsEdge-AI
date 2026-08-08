import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.bookmaker import Bookmaker
from app.models.odds_movement import OddsMovement
from app.models.odds_snapshot import OddsSnapshot
from app.services.odds_warehouse_foundation_service import (
    ensure_bookmaker,
    implied_probability,
    record_odds,
)


class OddsWarehouseFoundationTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite:///:memory:"
        )
        Base.metadata.create_all(bind=engine)

        Session = sessionmaker(bind=engine)
        self.db = Session()

    def tearDown(self):
        self.db.close()

    def test_implied_probability(self):
        self.assertEqual(
            implied_probability(2.0),
            50.0,
        )

    def test_bookmaker_created_once(self):
        first = ensure_bookmaker(
            self.db,
            code="PADDYPOWER",
            name="Paddy Power",
            priority=10,
        )

        second = ensure_bookmaker(
            self.db,
            code="paddypower",
            name="Paddy Power",
            priority=10,
        )

        self.assertEqual(
            first.id,
            second.id,
        )

    def test_initial_snapshot_has_no_movement(self):
        result = record_odds(
            self.db,
            fixture_id=101,
            bookmaker_code="paddypower",
            market="match_winner",
            selection="Alpha",
            decimal_odds=2.10,
        )

        self.assertTrue(
            result.snapshot_created
        )

        self.assertFalse(
            result.movement_created
        )

        self.assertEqual(
            self.db.query(OddsSnapshot).count(),
            1,
        )

        self.assertEqual(
            self.db.query(OddsMovement).count(),
            0,
        )

    def test_price_change_creates_movement(self):
        first_time = datetime(
            2026,
            8,
            8,
            10,
            0,
        )

        record_odds(
            self.db,
            fixture_id=101,
            bookmaker_code="bet365",
            market="match_winner",
            selection="Alpha",
            decimal_odds=2.10,
            captured_at=first_time,
        )

        result = record_odds(
            self.db,
            fixture_id=101,
            bookmaker_code="bet365",
            market="match_winner",
            selection="Alpha",
            decimal_odds=2.00,
            captured_at=(
                first_time
                + timedelta(minutes=5)
            ),
        )

        self.assertTrue(
            result.movement_created
        )

        movement = (
            self.db.query(OddsMovement)
            .first()
        )

        self.assertEqual(
            movement.direction,
            "shortening",
        )

        self.assertEqual(
            movement.previous_odds,
            2.10,
        )

        self.assertEqual(
            movement.new_odds,
            2.00,
        )

    def test_unchanged_price_is_not_duplicated(self):
        record_odds(
            self.db,
            fixture_id=101,
            bookmaker_code="paddypower",
            market="match_winner",
            selection="Alpha",
            decimal_odds=2.10,
        )

        result = record_odds(
            self.db,
            fixture_id=101,
            bookmaker_code="paddypower",
            market="match_winner",
            selection="Alpha",
            decimal_odds=2.10,
        )

        self.assertFalse(
            result.snapshot_created
        )

        self.assertEqual(
            self.db.query(OddsSnapshot).count(),
            1,
        )


if __name__ == "__main__":
    unittest.main()
