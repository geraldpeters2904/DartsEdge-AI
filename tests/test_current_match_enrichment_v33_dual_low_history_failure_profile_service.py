import unittest

from app.services.current_match_enrichment_v33_dual_low_history_failure_profile_service import (
    CurrentMatchEnrichmentV33DualLowHistoryFailureProfileService,
)


class CurrentMatchEnrichmentV33DualLowHistoryFailureProfileServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33DualLowHistoryFailureProfileService()
        )

    def test_feature_values(self):
        rows = (
            {
                "contributions": (
                    {
                        "feature_name": "scoring_power",
                        "weighted_score": 0.06,
                        "supports": True,
                    },
                    {
                        "feature_name": "recent_win_rate",
                        "weighted_score": 0.10,
                        "supports": True,
                    },
                ),
            },
            {
                "contributions": (
                    {
                        "feature_name": "scoring_power",
                        "weighted_score": -0.03,
                        "supports": False,
                    },
                ),
            },
        )

        result = self.service._feature_values(
            "scoring_power",
            rows,
        )

        self.assertEqual(
            result["observations"],
            2,
        )

        self.assertEqual(
            result["supporting"],
            1,
        )

        self.assertEqual(
            result["weighted"],
            (0.06, -0.03),
        )

    def test_feature_profile_compares_correct_and_incorrect(self):
        correct_rows = (
            {
                "contributions": (
                    {
                        "feature_name": "recent_win_rate",
                        "weighted_score": 0.10,
                        "supports": True,
                    },
                ),
            },
            {
                "contributions": (
                    {
                        "feature_name": "recent_win_rate",
                        "weighted_score": -0.05,
                        "supports": False,
                    },
                ),
            },
        )

        incorrect_rows = (
            {
                "contributions": (
                    {
                        "feature_name": "recent_win_rate",
                        "weighted_score": 0.10,
                        "supports": True,
                    },
                ),
            },
            {
                "contributions": (
                    {
                        "feature_name": "recent_win_rate",
                        "weighted_score": 0.10,
                        "supports": True,
                    },
                ),
            },
        )

        result = self.service._feature_profile(
            "recent_win_rate",
            correct_rows,
            incorrect_rows,
        )

        self.assertEqual(
            result.correct_support_rate,
            50.0,
        )

        self.assertEqual(
            result.incorrect_support_rate,
            100.0,
        )

        self.assertEqual(
            result.support_rate_gap,
            50.0,
        )

        self.assertEqual(
            result.correct_average_weighted_score,
            0.025,
        )

        self.assertEqual(
            result.incorrect_average_weighted_score,
            0.10,
        )

        self.assertEqual(
            result.correct_average_absolute_weighted_score,
            0.075,
        )

        self.assertEqual(
            result.incorrect_average_absolute_weighted_score,
            0.10,
        )

    def test_difference(self):
        self.assertEqual(
            self.service._difference(
                70.0,
                50.0,
            ),
            20.0,
        )

        self.assertIsNone(
            self.service._difference(
                None,
                50.0,
            )
        )

    def test_average(self):
        self.assertEqual(
            self.service._average(
                (0.02, 0.04, 0.06),
            ),
            0.04,
        )

        self.assertIsNone(
            self.service._average(())
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

    def test_rejects_invalid_history_threshold(self):
        with self.assertRaisesRegex(
            ValueError,
            "greater than zero",
        ):
            self.service.analyse(
                object(),
                offsets=(100,),
                history_threshold=0,
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


if __name__ == "__main__":
    unittest.main()
