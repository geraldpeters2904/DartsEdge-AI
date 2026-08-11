import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_wrong_consensus_aggregate_service import (
    CurrentMatchEnrichmentV33WrongConsensusAggregateService,
)


def feature(
    name,
    *,
    correct_supporting,
    incorrect_supporting,
    correct_strength,
    incorrect_strength,
):
    return SimpleNamespace(
        feature_name=name,
        correct_supporting=correct_supporting,
        incorrect_supporting=incorrect_supporting,
        correct_average_support_strength=correct_strength,
        incorrect_average_support_strength=incorrect_strength,
    )


def window(*features):
    return SimpleNamespace(
        features=features,
    )


class FakeWrongConsensusService:
    def __init__(self, report):
        self.report = report
        self.calls = []

    def analyse(self, db, **kwargs):
        self.calls.append(kwargs)
        return self.report


class CurrentMatchEnrichmentV33WrongConsensusAggregateServiceTests(
    unittest.TestCase
):
    def test_summarise_feature_calculates_rate_and_strength_gaps(self):
        values = {
            "correct_supporting": 20,
            "incorrect_supporting": 18,
            "correct_strength_total": 1.0,
            "correct_strength_count": 20,
            "incorrect_strength_total": 1.08,
            "incorrect_strength_count": 18,
        }

        item = (
            CurrentMatchEnrichmentV33WrongConsensusAggregateService
            ._summarise_feature(
                "maximums_strength",
                values,
                correct_total=40,
                incorrect_total=20,
            )
        )

        self.assertEqual(
            item.support_rate_correct,
            50.0,
        )

        self.assertEqual(
            item.support_rate_incorrect,
            90.0,
        )

        self.assertEqual(
            item.support_rate_gap,
            40.0,
        )

        self.assertEqual(
            item.correct_average_support_strength,
            0.05,
        )

        self.assertEqual(
            item.incorrect_average_support_strength,
            0.06,
        )

        self.assertEqual(
            item.support_strength_gap,
            0.01,
        )

    def test_analyse_aggregates_multiple_windows(self):
        source = SimpleNamespace(
            model_version="transparent-v3.3",
            total_high_agreement_matches=10,
            total_correct_high_agreement=6,
            total_incorrect_high_agreement=4,
            windows=(
                window(
                    feature(
                        "scoring_power",
                        correct_supporting=3,
                        incorrect_supporting=2,
                        correct_strength=0.04,
                        incorrect_strength=0.05,
                    ),
                ),
                window(
                    feature(
                        "scoring_power",
                        correct_supporting=2,
                        incorrect_supporting=1,
                        correct_strength=0.06,
                        incorrect_strength=0.07,
                    ),
                ),
            ),
        )

        fake = FakeWrongConsensusService(
            source
        )

        service = (
            CurrentMatchEnrichmentV33WrongConsensusAggregateService(
                wrong_consensus_service=fake,
            )
        )

        result = service.analyse(
            object(),
            offsets=(1, 2),
        )

        item = result.features[0]

        self.assertEqual(
            item.correct_supporting,
            5,
        )

        self.assertEqual(
            item.incorrect_supporting,
            3,
        )

        self.assertEqual(
            item.support_rate_correct,
            83.333,
        )

        self.assertEqual(
            item.support_rate_incorrect,
            75.0,
        )

        self.assertAlmostEqual(
            item.correct_average_support_strength,
            0.048,
            places=6,
        )

        self.assertAlmostEqual(
            item.incorrect_average_support_strength,
            0.056667,
            places=6,
        )

        self.assertEqual(
            len(fake.calls),
            1,
        )

    def test_weighted_average(self):
        self.assertEqual(
            CurrentMatchEnrichmentV33WrongConsensusAggregateService
            ._weighted_average(
                1.5,
                3,
            ),
            0.5,
        )

        self.assertIsNone(
            CurrentMatchEnrichmentV33WrongConsensusAggregateService
            ._weighted_average(
                0.0,
                0,
            )
        )

    def test_percentage(self):
        self.assertEqual(
            CurrentMatchEnrichmentV33WrongConsensusAggregateService
            ._percentage(
                3,
                4,
            ),
            75.0,
        )

        self.assertIsNone(
            CurrentMatchEnrichmentV33WrongConsensusAggregateService
            ._percentage(
                0,
                0,
            )
        )

    def test_difference(self):
        self.assertEqual(
            CurrentMatchEnrichmentV33WrongConsensusAggregateService
            ._difference(
                60.0,
                50.0,
            ),
            10.0,
        )

        self.assertIsNone(
            CurrentMatchEnrichmentV33WrongConsensusAggregateService
            ._difference(
                None,
                50.0,
            )
        )

    def test_requires_offsets(self):
        service = (
            CurrentMatchEnrichmentV33WrongConsensusAggregateService()
        )

        with self.assertRaisesRegex(
            ValueError,
            "at least one",
        ):
            service.analyse(
                object(),
                offsets=(),
            )


if __name__ == "__main__":
    unittest.main()
