import unittest
from datetime import date, datetime
from types import SimpleNamespace

from app.services.odds_warehouse_service import (
    build_market_view,
)


def snapshot(
    row_id,
    bookmaker,
    odds,
    hour,
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
        captured_at=datetime(
            2026,
            8,
            7,
            hour,
            0,
        ),
        provider_id="test",
    )


def analysis(
    bookmaker,
    *,
    opening,
    latest,
    movement,
    direction,
    volatility,
):
    return SimpleNamespace(
        id=1,
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
        opening_odds=opening,
        latest_odds=latest,
        best_odds=max(
            opening,
            latest,
        ),
        closing_odds=None,
        movement_percent=movement,
        implied_probability_change_points=0.0,
        movement_direction=direction,
        volatility=volatility,
        update_count=2,
        clv_percent=None,
        probability_clv_points=None,
        beat_closing_line=None,
        analysed_at=datetime(
            2026,
            8,
            7,
            12,
            0,
        ),
    )


class OddsWarehouseServiceTests(
    unittest.TestCase
):
    def test_prefers_best_latest_price(self):
        report = build_market_view(
            snapshots=[
                snapshot(
                    1,
                    "PaddyPower",
                    1.90,
                    8,
                ),
                snapshot(
                    2,
                    "Bet365",
                    1.95,
                    8,
                ),
                snapshot(
                    3,
                    "Paddy Power",
                    2.00,
                    10,
                ),
            ],
        )

        self.assertEqual(
            report.best_price.bookmaker,
            "Paddy Power",
        )

        self.assertEqual(
            report.best_price.decimal_odds,
            2.0,
        )

        self.assertEqual(
            report.paddy_power.decimal_odds,
            2.0,
        )

        self.assertEqual(
            report.bet365.decimal_odds,
            1.95,
        )

    def test_uses_priority_market_analysis(self):
        report = build_market_view(
            snapshots=[
                snapshot(
                    1,
                    "Bet365",
                    1.90,
                    8,
                ),
                snapshot(
                    2,
                    "Paddy Power",
                    1.88,
                    8,
                ),
            ],
            analyses=[
                analysis(
                    "Bet365",
                    opening=1.90,
                    latest=1.82,
                    movement=-4.21,
                    direction=(
                        "shortening"
                    ),
                    volatility="medium",
                ),
                analysis(
                    "Paddy Power",
                    opening=1.88,
                    latest=1.80,
                    movement=-4.26,
                    direction=(
                        "shortening"
                    ),
                    volatility="low",
                ),
            ],
        )

        self.assertEqual(
            report.opening_odds,
            1.88,
        )

        self.assertEqual(
            report.latest_odds,
            1.80,
        )

        self.assertEqual(
            report.volatility,
            "low",
        )

    def test_empty_snapshots_return_none(self):
        self.assertIsNone(
            build_market_view(
                snapshots=[]
            )
        )


if __name__ == "__main__":
    unittest.main()
