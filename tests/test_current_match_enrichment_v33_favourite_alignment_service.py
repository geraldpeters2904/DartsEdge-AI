import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_favourite_alignment_service import (
    CurrentMatchEnrichmentV33FavouriteAlignmentService,
)


def contribution(
    name,
    weighted,
):
    return SimpleNamespace(
        feature_name=name,
        weighted_score=weighted,
    )


class CurrentMatchEnrichmentV33FavouriteAlignmentServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33FavouriteAlignmentService()
        )

    def test_supporting_and_opposing_are_classified_for_player_a_favourite(
        self,
    ):
        selected = (
            {
                "correct": True,
                "favourite_is_a": True,
                "contributions": (
                    contribution(
                        "scoring_power",
                        0.05,
                    ),
                    contribution(
                        "finishing_strength",
                        -0.02,
                    ),
                ),
            },
        )

        results = {
            item.feature_name: item
            for item in self.service._feature_alignments(
                selected
            )
        }

        scoring = results[
            "scoring_power"
        ]

        finishing = results[
            "finishing_strength"
        ]

        self.assertEqual(
            scoring.supporting,
            1,
        )
        self.assertEqual(
            scoring.opposing,
            0,
        )
        self.assertEqual(
            scoring.supporting_correct,
            1,
        )

        self.assertEqual(
            finishing.supporting,
            0,
        )
        self.assertEqual(
            finishing.opposing,
            1,
        )
        self.assertEqual(
            finishing.opposing_correct,
            1,
        )

    def test_player_b_favourite_reverses_alignment_direction(
        self,
    ):
        selected = (
            {
                "correct": False,
                "favourite_is_a": False,
                "contributions": (
                    contribution(
                        "recent_win_rate",
                        -0.04,
                    ),
                    contribution(
                        "maximums_strength",
                        0.03,
                    ),
                ),
            },
        )

        results = {
            item.feature_name: item
            for item in self.service._feature_alignments(
                selected
            )
        }

        recent = results[
            "recent_win_rate"
        ]

        maximums = results[
            "maximums_strength"
        ]

        self.assertEqual(
            recent.supporting,
            1,
        )
        self.assertEqual(
            recent.supporting_incorrect,
            1,
        )

        self.assertEqual(
            maximums.opposing,
            1,
        )
        self.assertEqual(
            maximums.opposing_incorrect,
            1,
        )

    def test_neutral_contribution_is_counted(self):
        selected = (
            {
                "correct": True,
                "favourite_is_a": True,
                "contributions": (
                    contribution(
                        "overall_strength",
                        0.0,
                    ),
                ),
            },
        )

        result = (
            self.service._feature_alignments(
                selected
            )[0]
        )

        self.assertEqual(
            result.observations,
            1,
        )

        self.assertEqual(
            result.neutral,
            1,
        )

        self.assertEqual(
            result.supporting,
            0,
        )

        self.assertEqual(
            result.opposing,
            0,
        )

    def test_support_accuracy_is_calculated(self):
        selected = (
            {
                "correct": True,
                "favourite_is_a": True,
                "contributions": (
                    contribution(
                        "scoring_power",
                        0.05,
                    ),
                ),
            },
            {
                "correct": False,
                "favourite_is_a": True,
                "contributions": (
                    contribution(
                        "scoring_power",
                        0.04,
                    ),
                ),
            },
            {
                "correct": True,
                "favourite_is_a": True,
                "contributions": (
                    contribution(
                        "scoring_power",
                        0.03,
                    ),
                ),
            },
        )

        result = (
            self.service._feature_alignments(
                selected
            )[0]
        )

        self.assertEqual(
            result.supporting,
            3,
        )

        self.assertEqual(
            result.support_accuracy,
            66.667,
        )

        self.assertEqual(
            result.support_percentage,
            100.0,
        )

    def test_strength_averages_are_absolute(self):
        selected = (
            {
                "correct": True,
                "favourite_is_a": True,
                "contributions": (
                    contribution(
                        "scoring_power",
                        0.06,
                    ),
                ),
            },
            {
                "correct": True,
                "favourite_is_a": True,
                "contributions": (
                    contribution(
                        "scoring_power",
                        -0.02,
                    ),
                ),
            },
        )

        result = (
            self.service._feature_alignments(
                selected
            )[0]
        )

        self.assertEqual(
            result.average_support_strength,
            0.06,
        )

        self.assertEqual(
            result.average_opposition_strength,
            0.02,
        )

    def test_features_are_sorted_by_name(self):
        selected = (
            {
                "correct": True,
                "favourite_is_a": True,
                "contributions": (
                    contribution(
                        "z_feature",
                        0.01,
                    ),
                    contribution(
                        "a_feature",
                        0.02,
                    ),
                ),
            },
        )

        results = (
            self.service._feature_alignments(
                selected
            )
        )

        self.assertEqual(
            [
                item.feature_name
                for item in results
            ],
            [
                "a_feature",
                "z_feature",
            ],
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
