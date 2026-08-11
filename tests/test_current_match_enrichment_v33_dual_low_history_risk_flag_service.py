import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_dual_low_history_risk_flag_service import (
    CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService,
)


class CurrentMatchEnrichmentV33DualLowHistoryRiskFlagServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService()
        )

    @staticmethod
    def _prediction(
        *,
        predicted_winner="A",
        scores=(),
    ):
        return SimpleNamespace(
            predicted_winner=predicted_winner,
            player_a_name="A",
            player_b_name="B",
            contributions=tuple(
                SimpleNamespace(
                    weighted_score=value,
                )
                for value in scores
            ),
        )

    def test_feature_agreement_100_for_all_supporting(self):
        prediction = self._prediction(
            scores=(0.10, 0.05, 0.02),
        )

        self.assertEqual(
            self.service._feature_agreement(
                prediction,
            ),
            100.0,
        )

    def test_feature_agreement_handles_player_b(self):
        prediction = self._prediction(
            predicted_winner="B",
            scores=(-0.10, -0.05, -0.02),
        )

        self.assertEqual(
            self.service._feature_agreement(
                prediction,
            ),
            100.0,
        )

    def test_feature_agreement_counts_opposition(self):
        prediction = self._prediction(
            scores=(0.10, 0.05, -0.02, 0.03),
        )

        self.assertEqual(
            self.service._feature_agreement(
                prediction,
            ),
            75.0,
        )

    def test_feature_agreement_ignores_zero_weight(self):
        prediction = self._prediction(
            scores=(0.10, 0.0, 0.05),
        )

        self.assertEqual(
            self.service._feature_agreement(
                prediction,
            ),
            100.0,
        )

    def test_feature_agreement_none_without_active_features(self):
        prediction = self._prediction(
            scores=(0.0, 0.0),
        )

        self.assertIsNone(
            self.service._feature_agreement(
                prediction,
            )
        )

    def test_population_calculates_accuracy(self):
        records = (
            {
                "correct": True,
                "probability_correct": 0.70,
            },
            {
                "correct": False,
                "probability_correct": 0.30,
            },
            {
                "correct": True,
                "probability_correct": 0.65,
            },
            {
                "correct": False,
                "probability_correct": 0.35,
            },
        )

        result = self.service._population(
            "test",
            records,
        )

        self.assertEqual(
            result.predictions,
            4,
        )

        self.assertEqual(
            result.correct,
            2,
        )

        self.assertEqual(
            result.accuracy,
            50.0,
        )

    def test_population_probability_metrics(self):
        records = (
            {
                "correct": True,
                "probability_correct": 0.70,
            },
            {
                "correct": False,
                "probability_correct": 0.30,
            },
        )

        result = self.service._population(
            "test",
            records,
        )

        self.assertAlmostEqual(
            result.brier_score,
            0.29,
            places=6,
        )

        self.assertAlmostEqual(
            result.log_loss,
            0.780324,
            places=6,
        )

    def test_empty_population(self):
        result = self.service._population(
            "empty",
            (),
        )

        self.assertEqual(
            result.predictions,
            0,
        )

        self.assertEqual(
            result.correct,
            0,
        )

        self.assertIsNone(
            result.accuracy,
        )

        self.assertIsNone(
            result.brier_score,
        )

        self.assertIsNone(
            result.log_loss,
        )

    def test_rejects_invalid_probability_segment(self):
        with self.assertRaisesRegex(
            ValueError,
            "probability_lower",
        ):
            self.service.analyse(
                object(),
                probability_lower=70.0,
                probability_upper=65.0,
            )

    def test_rejects_invalid_history_threshold(self):
        with self.assertRaisesRegex(
            ValueError,
            "greater than zero",
        ):
            self.service.analyse(
                object(),
                history_threshold=0,
            )

    def test_rejects_invalid_agreement_threshold(self):
        with self.assertRaisesRegex(
            ValueError,
            "between 0 and 100",
        ):
            self.service.analyse(
                object(),
                agreement_threshold=101.0,
            )


if __name__ == "__main__":
    unittest.main()
