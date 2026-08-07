import unittest

from app.services.transparent_v3_weight_consensus import (
    TransparentV3WeightConsensusOptimiser,
)


class TransparentV3WeightConsensusTests(
    unittest.TestCase
):
    def test_high_confidence_requires_all_splits(self):
        self.assertEqual(
            TransparentV3WeightConsensusOptimiser
            ._confidence(1.0),
            "high",
        )

    def test_moderate_confidence_at_two_thirds(self):
        self.assertEqual(
            TransparentV3WeightConsensusOptimiser
            ._confidence(0.67),
            "moderate",
        )

    def test_difference_returns_left_minus_right(self):
        self.assertEqual(
            TransparentV3WeightConsensusOptimiser
            ._difference(
                0.28,
                0.26,
            ),
            0.02,
        )

    def test_difference_handles_missing_values(self):
        self.assertIsNone(
            TransparentV3WeightConsensusOptimiser
            ._difference(
                None,
                0.26,
            )
        )


if __name__ == "__main__":
    unittest.main()
