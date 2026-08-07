import unittest
from datetime import datetime
from types import SimpleNamespace

from app.services.market_consensus_service import (
    analyse_market_consensus,
    consensus_summary,
)


def row(row_id, bookmaker, odds, captured_at):
    return SimpleNamespace(
        id=row_id,
        bookmaker=bookmaker,
        decimal_odds=odds,
        captured_at=captured_at,
    )


class MarketConsensusServiceTests(unittest.TestCase):
    def test_high_agreement_scores_high(self):
        rows = [
            row(1, "Paddy Power", 1.90, datetime(2026, 8, 7, 8, 0)),
            row(2, "Bet365", 1.91, datetime(2026, 8, 7, 8, 0)),
            row(3, "Book C", 1.89, datetime(2026, 8, 7, 8, 0)),
        ]

        report = analyse_market_consensus(rows)

        self.assertGreaterEqual(report.consensus_score, 90)
        self.assertEqual(report.consensus_grade, "Very High")

    def test_coordinated_shortening_detected(self):
        rows = [
            row(1, "Paddy Power", 2.10, datetime(2026, 8, 7, 8, 0)),
            row(2, "Paddy Power", 1.90, datetime(2026, 8, 7, 10, 0)),
            row(3, "Bet365", 2.08, datetime(2026, 8, 7, 8, 0)),
            row(4, "Bet365", 1.92, datetime(2026, 8, 7, 10, 0)),
            row(5, "Book C", 2.05, datetime(2026, 8, 7, 8, 0)),
            row(6, "Book C", 1.91, datetime(2026, 8, 7, 10, 0)),
        ]

        report = analyse_market_consensus(rows)

        self.assertTrue(report.coordinated_move)
        self.assertEqual(report.steam_direction, "shortening")
        self.assertIn(
            report.steam_strength,
            {"light", "medium", "strong"},
        )

    def test_outlier_is_flagged(self):
        rows = [
            row(1, "Paddy Power", 1.90, datetime(2026, 8, 7, 10, 0)),
            row(2, "Bet365", 1.92, datetime(2026, 8, 7, 10, 0)),
            row(3, "Book C", 2.40, datetime(2026, 8, 7, 10, 0)),
        ]

        report = analyse_market_consensus(rows)

        self.assertIn("Book C", report.outlier_bookmakers)

    def test_single_bookmaker_is_limited(self):
        report = analyse_market_consensus([
            row(1, "Paddy Power", 1.90, datetime(2026, 8, 7, 10, 0))
        ])

        self.assertEqual(report.bookmaker_count, 1)
        self.assertIn(
            "Only one bookmaker is available, so consensus is limited.",
            report.caution_reasons,
        )

    def test_summary_is_json_ready(self):
        report = analyse_market_consensus([
            row(1, "Paddy Power", 1.90, datetime(2026, 8, 7, 10, 0)),
            row(2, "Bet365", 1.91, datetime(2026, 8, 7, 10, 0)),
        ])

        payload = consensus_summary(report)

        self.assertIsInstance(payload["bookmaker_points"], list)
        self.assertIn("consensus_score", payload)


if __name__ == "__main__":
    unittest.main()
