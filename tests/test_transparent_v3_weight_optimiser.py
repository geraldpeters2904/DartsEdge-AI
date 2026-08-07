import unittest

from app.services.transparent_v3_weight_optimiser import (
    WeightOptimisationScore,
)


class TransparentV3WeightOptimiserTests(
    unittest.TestCase
):
    def test_ranking_prefers_lower_brier(self):
        better = WeightOptimisationScore(
            accuracy=59.0,
            brier_score=0.24,
            log_loss=0.70,
        )
        worse = WeightOptimisationScore(
            accuracy=61.0,
            brier_score=0.26,
            log_loss=0.65,
        )

        self.assertLess(
            better.ranking_key(),
            worse.ranking_key(),
        )

    def test_log_loss_breaks_brier_tie(self):
        better = WeightOptimisationScore(
            accuracy=60.0,
            brier_score=0.25,
            log_loss=0.68,
        )
        worse = WeightOptimisationScore(
            accuracy=60.0,
            brier_score=0.25,
            log_loss=0.72,
        )

        self.assertLess(
            better.ranking_key(),
            worse.ranking_key(),
        )


if __name__ == "__main__":
    unittest.main()
