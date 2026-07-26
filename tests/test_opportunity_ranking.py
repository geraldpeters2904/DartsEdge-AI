import unittest
from datetime import date, timedelta

from app.services.opportunity_ranking_service import (
    rank_opportunities,
    rank_opportunity,
)


class OpportunityRankingTests(unittest.TestCase):
    def test_probability_accepts_fraction_or_percent(self):
        fraction = rank_opportunity({"probability": 0.68, "stars": 4})
        percent = rank_opportunity({"probability": 68, "stars": 4})
        self.assertEqual(fraction["probability"], 68.0)
        self.assertEqual(percent["probability"], 68.0)

    def test_missing_market_odds_is_not_confirmed_value(self):
        result = rank_opportunity({
            "probability": 70,
            "stars": 5,
            "confidence": "High",
            "fair_odds": 1.43,
        })
        self.assertFalse(result["is_value_confirmed"])
        self.assertEqual(result["action"], "Check odds")
        self.assertIsNone(result["edge_percent"])

    def test_positive_expected_value_is_confirmed(self):
        result = rank_opportunity({
            "probability": 70,
            "stars": 5,
            "confidence": "High",
            "fair_odds": 1.43,
            "market_odds": 1.70,
        })
        self.assertTrue(result["is_value_confirmed"])
        self.assertEqual(result["action"], "Consider")
        self.assertGreater(result["edge_percent"], 0)

    def test_confirmed_value_ranks_above_unpriced_signal(self):
        today = date(2026, 7, 25)
        opportunities = [
            {
                "selection": "A",
                "probability": 80,
                "stars": 5,
                "confidence": "High",
                "date": today,
            },
            {
                "selection": "B",
                "probability": 66,
                "stars": 4,
                "confidence": "Good",
                "date": today + timedelta(days=1),
                "market_odds": 1.80,
            },
        ]
        ranked = rank_opportunities(opportunities, today=today)
        self.assertEqual(ranked[0]["selection"], "B")
        self.assertTrue(ranked[0]["is_value_confirmed"])
        self.assertEqual([row["rank"] for row in ranked], [1, 2])


if __name__ == "__main__":
    unittest.main()
