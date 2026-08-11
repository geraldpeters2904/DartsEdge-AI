import unittest

from app.services.current_match_enrichment_v33_recent_win_rate_history_service import (
    CurrentMatchEnrichmentV33RecentWinRateHistoryService,
)


class CurrentMatchEnrichmentV33RecentWinRateHistoryServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33RecentWinRateHistoryService()
        )

    def test_build_band_calculates_accuracy_and_support(self):
        selected = (
            {
                "minimum_history": 1,
                "correct": True,
                "supports": True,
                "support_strength": 0.08,
            },
            {
                "minimum_history": 2,
                "correct": False,
                "supports": True,
                "support_strength": 0.06,
            },
            {
                "minimum_history": 3,
                "correct": True,
                "supports": False,
                "support_strength": None,
            },
        )

        result = self.service._build_band(
            selected,
            lower=0,
            upper=3,
        )

        self.assertEqual(
            result.band,
            "0-2",
        )

        self.assertEqual(
            result.predictions,
            2,
        )

        self.assertEqual(
            result.correct,
            1,
        )

        self.assertEqual(
            result.accuracy,
            50.0,
        )

        self.assertEqual(
            result.feature_supporting,
            2,
        )

        self.assertEqual(
            result.feature_supporting_correct,
            1,
        )

        self.assertEqual(
            result.feature_support_rate,
            100.0,
        )

        self.assertEqual(
            result.feature_support_accuracy,
            50.0,
        )

        self.assertEqual(
            result.average_support_strength,
            0.07,
        )

    def test_build_band_respects_history_boundaries(self):
        selected = (
            {
                "minimum_history": 2,
                "correct": True,
                "supports": True,
                "support_strength": 0.05,
            },
            {
                "minimum_history": 3,
                "correct": True,
                "supports": True,
                "support_strength": 0.05,
            },
            {
                "minimum_history": 4,
                "correct": True,
                "supports": True,
                "support_strength": 0.05,
            },
            {
                "minimum_history": 5,
                "correct": True,
                "supports": True,
                "support_strength": 0.05,
            },
        )

        result = self.service._build_band(
            selected,
            lower=3,
            upper=5,
        )

        self.assertEqual(
            result.predictions,
            2,
        )

    def test_empty_band(self):
        result = self.service._build_band(
            (),
            lower=5,
            upper=7,
        )

        self.assertEqual(
            result.predictions,
            0,
        )

        self.assertIsNone(
            result.accuracy,
        )

        self.assertIsNone(
            result.feature_support_rate,
        )

        self.assertIsNone(
            result.feature_support_accuracy,
        )

        self.assertIsNone(
            result.average_support_strength,
        )

    def test_average(self):
        self.assertEqual(
            self.service._average(
                (0.02, 0.04, 0.06),
            ),
            0.04,
        )

        self.assertIsNone(
            self.service._average(
                ()
            )
        )

    def test_percentage(self):
        self.assertEqual(
            self.service._percentage(
                3,
                4,
            ),
            75.0,
        )

        self.assertIsNone(
            self.service._percentage(
                0,
                0,
            )
        )

    def test_requires_offsets(self):
        with self.assertRaisesRegex(
            ValueError,
            "at least one",
        ):
            self.service.analyse(
                object(),
                offsets=(),
            )

    def test_rejects_invalid_probability_band(self):
        with self.assertRaisesRegex(
            ValueError,
            "must exceed",
        ):
            self.service.analyse(
                object(),
                offsets=(100,),
                probability_lower=70.0,
                probability_upper=65.0,
            )

    def test_rejects_invalid_window_size(self):
        with self.assertRaisesRegex(
            ValueError,
            "greater than zero",
        ):
            self.service.analyse(
                object(),
                offsets=(100,),
                window_size=0,
            )


if __name__ == "__main__":
    unittest.main()
