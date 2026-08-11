import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_wrong_consensus_service import (
    CurrentMatchEnrichmentV33WrongConsensusService,
)


def contribution(
    feature_name,
    weighted_score,
):
    return SimpleNamespace(
        feature_name=feature_name,
        weighted_score=weighted_score,
    )


class CurrentMatchEnrichmentV33WrongConsensusServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33WrongConsensusService()
        )

    def test_feature_summary_compares_support_rates(self):
        correct_rows = (
            {
                "supporting": (
                    contribution(
                        "maximums_strength",
                        0.05,
                    ),
                ),
            },
            {
                "supporting": (),
            },
        )

        incorrect_rows = (
            {
                "supporting": (
                    contribution(
                        "maximums_strength",
                        0.06,
                    ),
                ),
            },
            {
                "supporting": (
                    contribution(
                        "maximums_strength",
                        0.04,
                    ),
                ),
            },
        )

        result = self.service._feature_summary(
            "maximums_strength",
            correct_rows,
            incorrect_rows,
        )

        self.assertEqual(
            result.correct_supporting,
            1,
        )

        self.assertEqual(
            result.incorrect_supporting,
            2,
        )

        self.assertEqual(
            result.support_rate_correct,
            50.0,
        )

        self.assertEqual(
            result.support_rate_incorrect,
            100.0,
        )

        self.assertEqual(
            result.incorrect_minus_correct_support_rate,
            50.0,
        )

    def test_feature_summary_averages_strength(self):
        correct_rows = (
            {
                "supporting": (
                    contribution(
                        "scoring_power",
                        0.04,
                    ),
                    contribution(
                        "maximums_strength",
                        0.02,
                    ),
                ),
            },
            {
                "supporting": (
                    contribution(
                        "scoring_power",
                        0.08,
                    ),
                ),
            },
        )

        result = self.service._feature_summary(
            "scoring_power",
            correct_rows,
            (),
        )

        self.assertEqual(
            result.correct_average_support_strength,
            0.06,
        )

        self.assertIsNone(
            result.incorrect_average_support_strength,
        )

    def test_difference(self):
        self.assertEqual(
            self.service._difference(
                80.0,
                60.0,
            ),
            20.0,
        )

        self.assertIsNone(
            self.service._difference(
                None,
                60.0,
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

    def test_rejects_invalid_agreement_lower(self):
        with self.assertRaisesRegex(
            ValueError,
            "between 0 and 100",
        ):
            self.service.analyse(
                object(),
                offsets=(100,),
                agreement_lower=101.0,
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
