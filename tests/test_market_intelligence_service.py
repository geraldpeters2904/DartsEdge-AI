import unittest
from datetime import date, datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.market_snapshot_analysis import (
    MarketSnapshotAnalysis,
)
from app.services.market_intelligence_service import (
    analyse_bookmaker_market,
    bookmaker_scorecards,
    upsert_market_analysis,
)


def snapshot(
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


class MarketIntelligenceServiceTests(
    unittest.TestCase
):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={
                "check_same_thread": False
            },
            poolclass=StaticPool,
        )

        Base.metadata.create_all(
            engine
        )

        self.db = sessionmaker(
            bind=engine
        )()

    def tearDown(self):
        self.db.close()

    def rows(self):
        return [
            snapshot(
                1,
                "PaddyPower",
                2.00,
                datetime(
                    2026,
                    8,
                    7,
                    8,
                    0,
                ),
            ),
            snapshot(
                2,
                "Paddy Power",
                1.90,
                datetime(
                    2026,
                    8,
                    7,
                    9,
                    0,
                ),
            ),
            snapshot(
                3,
                "Paddy Power",
                1.80,
                datetime(
                    2026,
                    8,
                    7,
                    10,
                    0,
                ),
            ),
        ]

    def test_analyses_bookmaker_history(self):
        report = (
            analyse_bookmaker_market(
                self.rows()
            )
        )

        self.assertEqual(
            report.bookmaker,
            "Paddy Power",
        )
        self.assertEqual(
            report.opening_odds,
            2.0,
        )
        self.assertEqual(
            report.latest_odds,
            1.8,
        )
        self.assertEqual(
            report.best_odds,
            2.0,
        )
        self.assertEqual(
            report.movement_direction,
            "shortening",
        )
        self.assertEqual(
            report.update_count,
            3,
        )
        self.assertIsNone(
            report.closing_odds
        )

    def test_can_add_closing_line_later(self):
        report = (
            analyse_bookmaker_market(
                self.rows(),
                closing_odds=1.70,
            )
        )

        self.assertEqual(
            report.closing_odds,
            1.70,
        )
        self.assertGreater(
            report.clv_percent,
            0,
        )
        self.assertTrue(
            report.beat_closing_line
        )

    def test_upsert_preserves_opening_price(self):
        first = (
            analyse_bookmaker_market(
                self.rows()[:2]
            )
        )

        row, created = (
            upsert_market_analysis(
                self.db,
                first,
            )
        )

        self.assertTrue(
            created
        )
        self.assertEqual(
            row.opening_odds,
            2.0,
        )

        second = (
            analyse_bookmaker_market(
                self.rows()
            )
        )

        row, created = (
            upsert_market_analysis(
                self.db,
                second,
            )
        )

        self.assertFalse(
            created
        )
        self.assertEqual(
            row.opening_odds,
            2.0,
        )
        self.assertEqual(
            row.latest_odds,
            1.8,
        )
        self.assertEqual(
            self.db.query(
                MarketSnapshotAnalysis
            ).count(),
            1,
        )

    def test_bookmaker_scorecard_is_safe_without_clv(self):
        report = (
            analyse_bookmaker_market(
                self.rows()
            )
        )

        upsert_market_analysis(
            self.db,
            report,
        )

        scorecards = (
            bookmaker_scorecards(
                self.db
            )
        )

        self.assertEqual(
            scorecards[0][
                "bookmaker"
            ],
            "Paddy Power",
        )
        self.assertEqual(
            scorecards[0][
                "markets"
            ],
            1,
        )
        self.assertIsNone(
            scorecards[0][
                "average_clv_percent"
            ]
        )


if __name__ == "__main__":
    unittest.main()
