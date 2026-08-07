import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.routes.odds_warehouse import _latest_market_rows


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def order_by(self, *args):
        return self

    def limit(self, value):
        self.rows = self.rows[:value]
        return self

    def all(self):
        return self.rows


class FakeDb:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return FakeQuery(list(self.rows))


class OddsWarehouseConsensusRouteTests(unittest.TestCase):
    def test_route_adds_consensus_payload(self):
        rows = [
            SimpleNamespace(
                id=1,
                fixture_date="2026-08-07",
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                market="match_winner",
                selection="Alpha",
                bookmaker="Paddy Power",
                decimal_odds=2.10,
                captured_at=datetime(2026, 8, 7, 8, 0),
            ),
            SimpleNamespace(
                id=2,
                fixture_date="2026-08-07",
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                market="match_winner",
                selection="Alpha",
                bookmaker="Paddy Power",
                decimal_odds=1.90,
                captured_at=datetime(2026, 8, 7, 10, 0),
            ),
            SimpleNamespace(
                id=3,
                fixture_date="2026-08-07",
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                market="match_winner",
                selection="Alpha",
                bookmaker="Bet365",
                decimal_odds=2.08,
                captured_at=datetime(2026, 8, 7, 8, 0),
            ),
            SimpleNamespace(
                id=4,
                fixture_date="2026-08-07",
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                market="match_winner",
                selection="Alpha",
                bookmaker="Bet365",
                decimal_odds=1.92,
                captured_at=datetime(2026, 8, 7, 10, 0),
            ),
        ]

        result = _latest_market_rows(FakeDb(rows))

        self.assertIsNotNone(result[0]["consensus"])
        self.assertEqual(
            result[0]["consensus"]["steam_direction"],
            "shortening",
        )
        self.assertTrue(
            result[0]["consensus"]["coordinated_move"]
        )

    def test_template_shows_market_consensus_columns(self):
        text = Path(
            "app/templates/odds_warehouse.html"
        ).read_text(encoding="utf-8")

        self.assertIn("Consensus", text)
        self.assertIn("Steam", text)
        self.assertIn("Outliers", text)
        self.assertIn("Strong consensus", text)


if __name__ == "__main__":
    unittest.main()
