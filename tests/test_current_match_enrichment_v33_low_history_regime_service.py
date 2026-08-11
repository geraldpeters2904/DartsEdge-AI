import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_low_history_regime_service import (
    CurrentMatchEnrichmentV33LowHistoryRegimeService,
)


def contribution(
    name,
    *,
    raw,
    normalised,
    weighted,
):
    return SimpleNamespace(
        feature_name=name,
        raw_edge=raw,
        normalised_edge=normalised,
        weighted_score=weighted,
    )


class CurrentMatchEnrichmentV33LowHistoryRegimeServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33LowHistoryRegimeService()
        )

    def test_feature_profiles_average_contributions(self):
        selected = (
            {
                "contributions": (
                    contribution(
                        "scoring_power",
                        raw=20.0,
                        normalised=0.125,
                        weighted=0.01875,
                    ),
                    contribution(
                        "finishing_strength",
                        raw=-10.0,
                        normalised=-0.0625,
                        weighted=-0.0075,
                    ),
                ),
            },
            {
                "contributions": (
                    contribution(
                        "scoring_power",
                        raw=-10.0,
                        normalised=-0.0625,
                        weighted=-0.009375,
                    ),
                    contribution(
                        "finishing_strength",
                        raw=30.0,
                        normalised=0.1875,
                        weighted=0.0225,
                    ),
                ),
            },
        )

        profiles = {
            item.feature_name: item
            for item in (
                self.service._feature_profiles(
                    selected
                )
            )
        }

        scoring = profiles[
            "scoring_power"
        ]

        self.assertEqual(
            scoring.average_raw_edge,
            5.0,
        )

        self.assertEqual(
            scoring.average_absolute_raw_edge,
            15.0,
        )

        self.assertEqual(
            scoring.average_normalised_edge,
            0.03125,
        )

        self.assertEqual(
            scoring.average_absolute_normalised_edge,
            0.09375,
        )

        self.assertEqual(
            scoring.average_weighted_score,
            0.004687,
        )

        self.assertEqual(
            scoring.average_absolute_weighted_score,
            0.014062,
        )

    def test_feature_profiles_are_sorted(self):
        selected = (
            {
                "contributions": (
                    contribution(
                        "z_feature",
                        raw=1,
                        normalised=0.1,
                        weighted=0.01,
                    ),
                    contribution(
                        "a_feature",
                        raw=1,
                        normalised=0.1,
                        weighted=0.01,
                    ),
                ),
            },
        )

        profiles = (
            self.service._feature_profiles(
                selected
            )
        )

        self.assertEqual(
            [
                item.feature_name
                for item in profiles
            ],
            [
                "a_feature",
                "z_feature",
            ],
        )

    def test_empty_feature_profiles(self):
        self.assertEqual(
            self.service._feature_profiles(
                ()
            ),
            (),
        )

    def test_average(self):
        self.assertEqual(
            self.service._average(
                [1, 2, 3]
            ),
            2.0,
        )

        self.assertIsNone(
            self.service._average(
                []
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

    def test_rejects_invalid_history_upper(self):
        with self.assertRaisesRegex(
            ValueError,
            "greater than zero",
        ):
            self.service.analyse(
                object(),
                offsets=(100,),
                history_upper=0,
            )


if __name__ == "__main__":
    unittest.main()
