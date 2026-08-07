import unittest
from types import SimpleNamespace

from app.services.advanced_player_feature_engine import (
    AdvancedPlayerFeatureEngine,
)


class AdvancedConsistencyFeatureTests(
    unittest.TestCase
):
    def test_standard_deviation(self):
        self.assertEqual(
            AdvancedPlayerFeatureEngine
            ._standard_deviation(
                [90.0, 90.0, 90.0]
            ),
            0.0,
        )

    def test_requires_two_values(self):
        self.assertIsNone(
            AdvancedPlayerFeatureEngine
            ._standard_deviation([90.0])
        )

    def test_profile_uses_recent_performances(self):
        performances = [
            SimpleNamespace(
                three_dart_average=value,
                checkout_percentage=40.0,
                scores_180=1,
            )
            for value in (
                90.0,
                92.0,
                94.0,
            )
        ]

        result = (
            AdvancedPlayerFeatureEngine
            ._consistency_profile(
                performances
            )
        )

        self.assertEqual(
            result.sample_matches,
            3,
        )
        self.assertGreater(
            result.three_dart_average_stddev,
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
