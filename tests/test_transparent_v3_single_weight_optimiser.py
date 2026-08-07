import unittest

from app.services.transparent_v3_single_weight_optimiser import (
    TransparentV3SingleWeightOptimiser,
    WeightCandidateResult,
)


class TransparentV3SingleWeightOptimiserTests(
    unittest.TestCase
):
    def test_ranking_prefers_lower_brier(self):
        better = WeightCandidateResult(
            weight=0.20,
            accuracy=58.0,
            brier_score=0.24,
            log_loss=0.70,
        )
        worse = WeightCandidateResult(
            weight=0.30,
            accuracy=61.0,
            brier_score=0.26,
            log_loss=0.65,
        )

        self.assertLess(
            better.ranking_key(),
            worse.ranking_key(),
        )

    def test_holdout_improvement_is_accepted(self):
        baseline = WeightCandidateResult(
            weight=0.15,
            accuracy=58.0,
            brier_score=0.27,
            log_loss=0.75,
        )
        candidate = WeightCandidateResult(
            weight=0.20,
            accuracy=58.0,
            brier_score=0.25,
            log_loss=0.71,
        )

        accepted, _ = (
            TransparentV3SingleWeightOptimiser
            ._recommendation(
                current_weight=0.15,
                recommended_weight=0.20,
                baseline=baseline,
                candidate=candidate,
            )
        )

        self.assertTrue(accepted)

    def test_failed_holdout_is_rejected(self):
        baseline = WeightCandidateResult(
            weight=0.15,
            accuracy=58.0,
            brier_score=0.25,
            log_loss=0.71,
        )
        candidate = WeightCandidateResult(
            weight=0.20,
            accuracy=60.0,
            brier_score=0.27,
            log_loss=0.69,
        )

        accepted, _ = (
            TransparentV3SingleWeightOptimiser
            ._recommendation(
                current_weight=0.15,
                recommended_weight=0.20,
                baseline=baseline,
                candidate=candidate,
            )
        )

        self.assertFalse(accepted)


if __name__ == "__main__":
    unittest.main()
