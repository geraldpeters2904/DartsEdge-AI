import tempfile
import unittest
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.services.expected_value_service import assess_value, best_prices, store_snapshot


class ExpectedValueEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db")
        engine = create_engine(f"sqlite:///{self.tmp.name}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close(); self.tmp.close()

    def test_positive_ev_and_kelly(self):
        result = assess_value(60, 2.0, "Example", 1000, 0.25, 5, 2)
        self.assertTrue(result.has_value)
        self.assertEqual(result.expected_value_percent, 20.0)
        self.assertGreater(result.recommended_stake, 0)

    def test_negative_ev_is_pass(self):
        result = assess_value(45, 2.0, "Example", 1000, 0.25, 5, 0)
        self.assertFalse(result.has_value)
        self.assertEqual(result.recommended_stake, 0)

    def test_invalid_odds_rejected(self):
        with self.assertRaises(ValueError):
            assess_value(60, 1.0, "Example", 1000, 0.25, 5)

    def test_duplicate_snapshot_is_not_inserted(self):
        kwargs = dict(fixture_date=date(2026, 7, 26), tournament="MODUS", player_a="A", player_b="B", market="match_winner", selection="A", bookmaker="Book", decimal_odds=2.1, captured_at=datetime(2026,7,26,8,0))
        _, first = store_snapshot(self.db, **kwargs)
        _, second = store_snapshot(self.db, **kwargs)
        self.assertTrue(first); self.assertFalse(second)

    def test_best_price_selects_highest_bookmaker_odds(self):
        common = dict(fixture_date=date(2026, 7, 26), tournament="MODUS", player_a="A", player_b="B", market="match_winner", selection="A")
        store_snapshot(self.db, **common, bookmaker="One", decimal_odds=1.9, captured_at=datetime(2026,7,26,8,0))
        store_snapshot(self.db, **common, bookmaker="Two", decimal_odds=2.1, captured_at=datetime(2026,7,26,8,1))
        rows = self.db.query(__import__('app.models.odds_snapshot', fromlist=['OddsSnapshot']).OddsSnapshot).all()
        self.assertEqual(best_prices(rows)[0].bookmaker, "Two")

if __name__ == "__main__": unittest.main()
