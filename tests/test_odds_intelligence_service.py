import unittest
from datetime import date, datetime, timedelta

from app.models.odds_snapshot import (
    OddsSnapshot,
)
from app.services.odds_intelligence_service import (
    analyse_snapshots,
    closing_line_value_percent,
)


def snapshot(
    *,
    odds,
    captured_at,
    bookmaker="Book",
    row_id=None,
):
    row = OddsSnapshot(
        fixture_date=date(
            2026,
            8,
            6,
        ),
        tournament="MODUS",
        player_a="Lewis Pride",
        player_b="Devon Petersen",
        market="match_winner",
        selection="Lewis Pride",
        bookmaker=bookmaker,
        decimal_odds=odds,
        captured_at=captured_at,
        provider_id="test",
        fingerprint=(
            f"{bookmaker}-{odds}-"
            f"{captured_at.isoformat()}"
        ),
    )

    row.id = row_id

    return row


class OddsIntelligenceServiceTests(
    unittest.TestCase
):
    def test_returns_none_without_snapshots(self):
        self.assertIsNone(
            analyse_snapshots([])
        )

    def test_calculates_shortening_market(self):
        opened = datetime(
            2026,
            8,
            6,
            9,
            0,
        )

        result = analyse_snapshots([
            snapshot(
                odds=2.00,
                captured_at=opened,
                bookmaker="Book A",
                row_id=1,
            ),
            snapshot(
                odds=1.80,
                captured_at=(
                    opened
                    + timedelta(
                        minutes=30
                    )
                ),
                bookmaker="Book B",
                row_id=2,
            ),
        ])

        self.assertIsNotNone(result)
        self.assertEqual(
            result.opening_price,
            2.0,
        )
        self.assertEqual(
            result.latest_price,
            1.8,
        )
        self.assertEqual(
            result.best_price,
            2.0,
        )
        self.assertEqual(
            result.market_direction,
            "shortening",
        )
        self.assertTrue(
            result.steam_move
        )
        self.assertFalse(
            result.drift_move
        )
        self.assertEqual(
            result.update_count,
            2,
        )
        self.assertEqual(
            result.bookmaker_count,
            2,
        )
        self.assertAlmostEqual(
            result.price_change_percent,
            -10.0,
        )
        self.assertAlmostEqual(
            result.implied_probability_change,
            5.556,
            places=3,
        )

    def test_calculates_drifting_market(self):
        opened = datetime(
            2026,
            8,
            6,
            9,
            0,
        )

        result = analyse_snapshots([
            snapshot(
                odds=1.80,
                captured_at=opened,
                row_id=1,
            ),
            snapshot(
                odds=2.00,
                captured_at=(
                    opened
                    + timedelta(
                        minutes=20
                    )
                ),
                row_id=2,
            ),
        ])

        self.assertEqual(
            result.market_direction,
            "drifting",
        )
        self.assertTrue(
            result.drift_move
        )
        self.assertFalse(
            result.steam_move
        )

    def test_small_movement_is_stable(self):
        opened = datetime(
            2026,
            8,
            6,
            9,
            0,
        )

        result = analyse_snapshots([
            snapshot(
                odds=2.00,
                captured_at=opened,
                row_id=1,
            ),
            snapshot(
                odds=2.005,
                captured_at=(
                    opened
                    + timedelta(
                        minutes=30
                    )
                ),
                row_id=2,
            ),
        ])

        self.assertEqual(
            result.market_direction,
            "stable",
        )
        self.assertFalse(
            result.steam_move
        )
        self.assertFalse(
            result.drift_move
        )

    def test_history_is_chronological(self):
        opened = datetime(
            2026,
            8,
            6,
            9,
            0,
        )

        result = analyse_snapshots([
            snapshot(
                odds=1.90,
                captured_at=(
                    opened
                    + timedelta(
                        minutes=20
                    )
                ),
                row_id=2,
            ),
            snapshot(
                odds=2.00,
                captured_at=opened,
                row_id=1,
            ),
        ])

        self.assertEqual(
            result.history[0]
            .decimal_odds,
            2.0,
        )
        self.assertEqual(
            result.history[-1]
            .decimal_odds,
            1.9,
        )

    def test_positive_clv_when_taken_price_beats_close(self):
        self.assertEqual(
            closing_line_value_percent(
                2.00,
                1.80,
            ),
            11.111,
        )

    def test_negative_clv_when_close_is_better(self):
        self.assertEqual(
            closing_line_value_percent(
                1.80,
                2.00,
            ),
            -10.0,
        )

    def test_invalid_clv_odds_fail(self):
        with self.assertRaises(
            ValueError
        ):
            closing_line_value_percent(
                1.0,
                2.0,
            )


if __name__ == "__main__":
    unittest.main()
