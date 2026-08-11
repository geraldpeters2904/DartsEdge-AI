import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_feature_reliability_service import (
    CurrentMatchEnrichmentV33FeatureReliabilityService,
)


def alignment(
    feature_name,
    *,
    supporting,
    supporting_correct,
    average_support_strength,
):
    return SimpleNamespace(
        feature_name=feature_name,
        supporting=supporting,
        supporting_correct=supporting_correct,
        average_support_strength=average_support_strength,
    )


def window(*items):
    return SimpleNamespace(
        feature_alignments=items,
    )


def report(
    *,
    model_version="transparent-v3.3",
    total_segment_matches=0,
    windows=(),
):
    return SimpleNamespace(
        model_version=model_version,
        total_segment_matches=total_segment_matches,
        windows=windows,
    )


class FakeAlignmentService:
    def __init__(
        self,
        *,
        strong_report,
        weak_report,
    ):
        self.strong_report = strong_report
        self.weak_report = weak_report
        self.calls = []

    def analyse(
        self,
        db,
        *,
        offsets,
        window_size,
        probability_lower,
        probability_upper,
        history_upper,
        competition_code,
    ):
        offsets = tuple(offsets)

        self.calls.append(
            (
                offsets,
                window_size,
                probability_lower,
                probability_upper,
                history_upper,
                competition_code,
            )
        )

        if offsets == (1, 2):
            return self.strong_report

        return self.weak_report


class CurrentMatchEnrichmentV33FeatureReliabilityServiceTests(
    unittest.TestCase
):
    def test_aggregates_support_counts_across_windows(self):
        source = report(
            total_segment_matches=20,
            windows=(
                window(
                    alignment(
                        "scoring_power",
                        supporting=10,
                        supporting_correct=8,
                        average_support_strength=0.05,
                    ),
                ),
                window(
                    alignment(
                        "scoring_power",
                        supporting=5,
                        supporting_correct=3,
                        average_support_strength=0.07,
                    ),
                ),
            ),
        )

        aggregated = (
            CurrentMatchEnrichmentV33FeatureReliabilityService
            ._aggregate_features(source)
        )

        scoring = aggregated[
            "scoring_power"
        ]

        self.assertEqual(
            scoring["supporting"],
            15,
        )

        self.assertEqual(
            scoring["supporting_correct"],
            11,
        )

        self.assertAlmostEqual(
            scoring["support_strength_total"],
            0.85,
            places=6,
        )

        self.assertEqual(
            scoring["support_strength_count"],
            15,
        )

    def test_compare_feature_calculates_deterioration(self):
        strong = {
            "supporting": 20,
            "supporting_correct": 16,
            "support_strength_total": 1.0,
            "support_strength_count": 20,
        }

        weak = {
            "supporting": 20,
            "supporting_correct": 10,
            "support_strength_total": 1.2,
            "support_strength_count": 20,
        }

        item = (
            CurrentMatchEnrichmentV33FeatureReliabilityService
            ._compare_feature(
                "maximums_strength",
                strong,
                weak,
            )
        )

        self.assertEqual(
            item.strong_support_accuracy,
            80.0,
        )

        self.assertEqual(
            item.weak_support_accuracy,
            50.0,
        )

        self.assertEqual(
            item.support_accuracy_change,
            -30.0,
        )

        self.assertEqual(
            item.reliability_deterioration,
            30.0,
        )

        self.assertEqual(
            item.strong_average_support_strength,
            0.05,
        )

        self.assertEqual(
            item.weak_average_support_strength,
            0.06,
        )

    def test_improvement_has_zero_deterioration(self):
        strong = {
            "supporting": 10,
            "supporting_correct": 5,
            "support_strength_total": 0.5,
            "support_strength_count": 10,
        }

        weak = {
            "supporting": 10,
            "supporting_correct": 7,
            "support_strength_total": 0.5,
            "support_strength_count": 10,
        }

        item = (
            CurrentMatchEnrichmentV33FeatureReliabilityService
            ._compare_feature(
                "feature",
                strong,
                weak,
            )
        )

        self.assertEqual(
            item.support_accuracy_change,
            20.0,
        )

        self.assertEqual(
            item.reliability_deterioration,
            0.0,
        )

    def test_missing_feature_side_is_supported(self):
        weak = {
            "supporting": 5,
            "supporting_correct": 2,
            "support_strength_total": 0.2,
            "support_strength_count": 5,
        }

        item = (
            CurrentMatchEnrichmentV33FeatureReliabilityService
            ._compare_feature(
                "feature",
                None,
                weak,
            )
        )

        self.assertEqual(
            item.strong_supporting,
            0,
        )

        self.assertIsNone(
            item.strong_support_accuracy,
        )

        self.assertEqual(
            item.weak_support_accuracy,
            40.0,
        )

        self.assertIsNone(
            item.reliability_deterioration,
        )

    def test_analyse_combines_strong_and_weak_reports(self):
        strong_report = report(
            total_segment_matches=30,
            windows=(
                window(
                    alignment(
                        "scoring_power",
                        supporting=20,
                        supporting_correct=16,
                        average_support_strength=0.05,
                    ),
                ),
            ),
        )

        weak_report = report(
            total_segment_matches=40,
            windows=(
                window(
                    alignment(
                        "scoring_power",
                        supporting=20,
                        supporting_correct=10,
                        average_support_strength=0.06,
                    ),
                ),
            ),
        )

        fake = FakeAlignmentService(
            strong_report=strong_report,
            weak_report=weak_report,
        )

        service = (
            CurrentMatchEnrichmentV33FeatureReliabilityService(
                alignment_service=fake,
            )
        )

        result = service.analyse(
            object(),
            strong_offsets=(1, 2),
            weak_offsets=(3, 4),
            window_size=500,
            probability_lower=65.0,
            probability_upper=70.0,
            history_upper=10,
            competition_code="MODUS",
        )

        self.assertEqual(
            result.model_version,
            "transparent-v3.3",
        )

        self.assertEqual(
            result.strong_segment_matches,
            30,
        )

        self.assertEqual(
            result.weak_segment_matches,
            40,
        )

        self.assertEqual(
            len(result.features),
            1,
        )

        self.assertEqual(
            result.features[0].reliability_deterioration,
            30.0,
        )

        self.assertEqual(
            len(fake.calls),
            2,
        )

    def test_rejects_overlapping_offsets(self):
        service = (
            CurrentMatchEnrichmentV33FeatureReliabilityService()
        )

        with self.assertRaisesRegex(
            ValueError,
            "cannot overlap",
        ):
            service.analyse(
                object(),
                strong_offsets=(1, 2),
                weak_offsets=(2, 3),
            )

    def test_requires_strong_offsets(self):
        service = (
            CurrentMatchEnrichmentV33FeatureReliabilityService()
        )

        with self.assertRaisesRegex(
            ValueError,
            "strong-regime",
        ):
            service.analyse(
                object(),
                strong_offsets=(),
                weak_offsets=(1,),
            )

    def test_requires_weak_offsets(self):
        service = (
            CurrentMatchEnrichmentV33FeatureReliabilityService()
        )

        with self.assertRaisesRegex(
            ValueError,
            "weak-regime",
        ):
            service.analyse(
                object(),
                strong_offsets=(1,),
                weak_offsets=(),
            )


if __name__ == "__main__":
    unittest.main()
