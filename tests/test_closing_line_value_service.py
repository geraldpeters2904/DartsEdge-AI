import unittest
from datetime import date, datetime
from types import SimpleNamespace

from app.services.closing_line_value_service import (
    build_price_lifecycle,
    calculate_clv,
    canonical_bookmaker,
)


def row(
    row_id,
    bookmaker,
    odds,
    captured_at,
):
    return SimpleNamespace(
        id=row_id,
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
        bookmaker=bookmaker,
        decimal_odds=odds,
        captured_at=captured_at,
    )


class ClosingLineValueServiceTests(
    unittest.TestCase
):
    def test_positive_clv_when_taken_price_beats_close(self):
        result = calculate_clv(
            taken_odds=2.10,
            closing_odds=1.90,
        )

        self.assertTrue(
            result.beat_close
        )
        self.assertGreater(
            result.odds_clv_percent,
            0,
        )
        self.assertGreater(
            result.probability_clv_points,
            0,
        )

    def test_negative_clv_when_price_drifts_after_bet(self):
        result = calculate_clv(
            taken_odds=1.80,
            closing_odds=2.00,
        )

        self.assertFalse(
            result.beat_close
        )
        self.assertLess(
            result.odds_clv_percent,
            0,
        )

    def test_builds_opening_latest_and_best(self):
        rows = [
            row(
                1,
                "PaddyPower",
                1.90,
                datetime(2026, 8, 7, 8, 0),
            ),
            row(
                2,
                "Bet365",
                2.05,
                datetime(2026, 8, 7, 9, 0),
            ),
            row(
                3,
                "Paddy Power",
                1.85,
                datetime(2026, 8, 7, 10, 0),
            ),
        ]

        lifecycle = build_price_lifecycle(
            rows
        )

        self.assertEqual(
            lifecycle.opening.decimal_odds,
            1.90,
        )
        self.assertEqual(
            lifecycle.latest.decimal_odds,
            1.85,
        )
        self.assertEqual(
            lifecycle.best.decimal_odds,
            2.05,
        )
        self.assertEqual(
            lifecycle.best.bookmaker,
            "Bet365",
        )
        self.assertEqual(
            lifecycle.update_count,
            3,
        )
        self.assertEqual(
            lifecycle.direction,
            "shortening",
        )

    def test_normalises_priority_bookmakers(self):
        self.assertEqual(
            canonical_bookmaker(
                "PaddyPower"
            ),
            "Paddy Power",
        )
        self.assertEqual(
            canonical_bookmaker(
                "bet 365"
            ),
            "Bet365",
        )

    def test_rejects_invalid_closing_odds(self):
        with self.assertRaises(
            ValueError
        ):
            calculate_clv(
                taken_odds=1.90,
                closing_odds=1.0,
            )


if __name__ == "__main__":
    unittest.main()
