import unittest
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.services.prediction_centre_service import (
    _matched_consensus,
)


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return list(self.rows)


class FakeDb:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return FakeQuery(self.rows)


class PredictionCentreConsensusTests(unittest.TestCase):
    def test_matches_fixture_and_selection(self):
        fixture = SimpleNamespace(
            date=date(2026, 8, 7),
            player_a="Alpha",
            player_b="Bravo",
        )

        rows = [
            SimpleNamespace(
                id=1,
                fixture_date=date(2026, 8, 7),
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
                fixture_date=date(2026, 8, 7),
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
                fixture_date=date(2026, 8, 7),
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
                fixture_date=date(2026, 8, 7),
                player_a="Alpha",
                player_b="Bravo",
                market="match_winner",
                selection="Alpha",
                bookmaker="Bet365",
                decimal_odds=1.92,
                captured_at=datetime(2026, 8, 7, 10, 0),
            ),
        ]

        payload = _matched_consensus(
            FakeDb(rows),
            fixture=fixture,
            opportunity={
                "selection": "Alpha",
            },
        )

        self.assertIsNotNone(payload)
        self.assertEqual(
            payload["steam_direction"],
            "shortening",
        )
        self.assertTrue(
            payload["coordinated_move"]
        )

    def test_no_odds_is_neutral(self):
        fixture = SimpleNamespace(
            date=date(2026, 8, 7),
            player_a="Alpha",
            player_b="Bravo",
        )

        payload = _matched_consensus(
            FakeDb([]),
            fixture=fixture,
            opportunity={
                "selection": "Alpha",
            },
        )

        self.assertIsNone(payload)


if __name__ == "__main__":
    unittest.main()
