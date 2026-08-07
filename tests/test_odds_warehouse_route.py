import unittest
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


class OddsWarehouseRouteTests(unittest.TestCase):
    def test_latest_market_rows_select_best_price(self):
        rows = [
            SimpleNamespace(
                id=1,
                fixture_date="2026-08-07",
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                market="match_winner",
                selection="Alpha",
                bookmaker="PaddyPower",
                decimal_odds=1.90,
                captured_at=1,
            ),
            SimpleNamespace(
                id=2,
                fixture_date="2026-08-07",
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                market="match_winner",
                selection="Alpha",
                bookmaker="Bet365",
                decimal_odds=2.00,
                captured_at=2,
            ),
        ]

        result = _latest_market_rows(FakeDb(rows))

        self.assertEqual(result[0]["best_bookmaker"], "Bet365")
        self.assertEqual(result[0]["best_odds"], 2.0)
        self.assertEqual(result[0]["paddy_power_odds"], 1.9)

    def test_template_contains_priority_books(self):
        text = Path(
            "app/templates/odds_warehouse.html"
        ).read_text(encoding="utf-8")

        self.assertIn("Paddy Power & Bet365", text)
        self.assertIn("Latest market prices", text)
        self.assertIn("All bookmakers", text)


if __name__ == "__main__":
    unittest.main()
