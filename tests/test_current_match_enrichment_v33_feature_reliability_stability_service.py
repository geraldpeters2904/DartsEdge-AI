import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_feature_reliability_stability_service import (
    CurrentMatchEnrichmentV33FeatureReliabilityStabilityService,
)


def alignment(
    feature_name,
    *,
    supporting,
    supporting_correct,
    support_accuracy,
    average_support_strength,
):
    return SimpleNamespace(
        feature_name=feature_name,
        supporting=supporting,
        supporting_correct=supporting_correct,
        support_accuracy=support_accuracy,
        average_support_strength=average_support_strength,
    )


def window(
    offset,
    *,
    segment_matches,
    accuracy,
    alignments,
):
    return SimpleNamespace(
        offset=offset,
        segment_matches=segment_matches,
        accuracy=accuracy,
        feature_alignments=alignments,
    )


class CurrentMatchEnrichmentV33FeatureReliabilityStabilityServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33FeatureReliabilityStabilityService()
        )

    def test_weighted_support_accuracy_uses_support_counts(self):
        rows = (
            SimpleNamespace(
                supporting=10,
                supporting_correct=8,
            ),
            SimpleNamespace(
                supporting=20,
                supporting_correct=10,
            ),
        )

        result = (
            self.service
            ._weighted_support_accuracy(
                rows
            )
        )

        self.assertEqual(
            result,
            60.0,
        )

    def test_correlation_detects_positive_relationship(self):
        result = (
            self.service._correlation(
                (50.0, 60.0, 70.0),
                (55.0, 65.0, 75.0),
            )
        )

        self.assertEqual(
            result,
            1.0,
        )

    def test_correlation_detects_negative_relationship(self):
        result = (
            self.service._correlation(
                (50.0, 60.0, 70.0),
                (75.0, 65.0, 55.0),
            )
        )

        self.assertEqual(
            result,
            -1.0,
        )

    def test_correlation_requires_three_points(self):
        result = (
            self.service._correlation(
                (50.0, 60.0),
                (55.0, 65.0),
            )
        )

        self.assertIsNone(
            result
        )

    def test_correlation_rejects_unequal_lengths(self):
        with self.assertRaisesRegex(
            ValueError,
            "equal lengths",
        ):
            self.service._correlation(
                (1.0, 2.0),
                (1.0,),
            )

    def test_summarise_feature_filters_small_support_windows(self):
        windows = (
            window(
                100,
                segment_matches=20,
                accuracy=75.0,
                alignments=(
                    alignment(
                        "maximums_strength",
                        supporting=10,
                        supporting_correct=8,
                        support_accuracy=80.0,
                        average_support_strength=0.05,
                    ),
                ),
            ),
            window(
                200,
                segment_matches=20,
                accuracy=50.0,
                alignments=(
                    alignment(
                        "maximums_strength",
                        supporting=3,
                        supporting_correct=1,
                        support_accuracy=33.333,
                        average_support_strength=0.06,
                    ),
                ),
            ),
            window(
                300,
                segment_matches=20,
                accuracy=60.0,
                alignments=(
                    alignment(
                        "maximums_strength",
                        supporting=10,
                        supporting_correct=5,
                        support_accuracy=50.0,
                        average_support_strength=0.055,
                    ),
                ),
            ),
        )

        result = (
            self.service._summarise_feature(
                "maximums_strength",
                windows,
                minimum_supporting=5,
            )
        )

        self.assertEqual(
            result.windows_with_evidence,
            2,
        )

        self.assertEqual(
            result.total_supporting,
            20,
        )

        self.assertEqual(
            result.average_support_accuracy,
            65.0,
        )

        self.assertEqual(
            result.minimum_support_accuracy,
            50.0,
        )

        self.assertEqual(
            result.maximum_support_accuracy,
            80.0,
        )

        self.assertEqual(
            result.support_accuracy_range,
            30.0,
        )

    def test_summarise_feature_calculates_correlation(self):
        windows = (
            window(
                100,
                segment_matches=20,
                accuracy=50.0,
                alignments=(
                    alignment(
                        "scoring_power",
                        supporting=10,
                        supporting_correct=5,
                        support_accuracy=50.0,
                        average_support_strength=0.05,
                    ),
                ),
            ),
            window(
                200,
                segment_matches=20,
                accuracy=60.0,
                alignments=(
                    alignment(
                        "scoring_power",
                        supporting=10,
                        supporting_correct=6,
                        support_accuracy=60.0,
                        average_support_strength=0.05,
                    ),
                ),
            ),
            window(
                300,
                segment_matches=20,
                accuracy=70.0,
                alignments=(
                    alignment(
                        "scoring_power",
                        supporting=10,
                        supporting_correct=7,
                        support_accuracy=70.0,
                        average_support_strength=0.05,
                    ),
                ),
            ),
        )

        result = (
            self.service._summarise_feature(
                "scoring_power",
                windows,
                minimum_supporting=5,
            )
        )

        self.assertEqual(
            result.segment_accuracy_correlation,
            1.0,
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

    def test_requires_positive_minimum_supporting(self):
        with self.assertRaisesRegex(
            ValueError,
            "greater than zero",
        ):
            self.service.analyse(
                object(),
                offsets=(100,),
                minimum_supporting=0,
            )


if __name__ == "__main__":
    unittest.main()
