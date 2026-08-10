import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_segmentation_service import (
    CurrentMatchEnrichmentV33SegmentationService,
)


def record(
    *,
    favourite_probability,
    confidence,
    correct,
    brier_score,
    log_loss,
    tournament="MODUS Super Series",
    stage="Group A",
):
    return SimpleNamespace(
        favourite_probability=favourite_probability,
        confidence=confidence,
        correct=correct,
        brier_score=brier_score,
        log_loss=log_loss,
        tournament=tournament,
        stage=stage,
    )


class CurrentMatchEnrichmentV33SegmentationServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33SegmentationService()
        )

    def test_numeric_probability_segment(self):
        records = (
            record(
                favourite_probability=52.0,
                confidence=50.0,
                correct=True,
                brier_score=0.20,
                log_loss=0.60,
            ),
            record(
                favourite_probability=54.0,
                confidence=50.0,
                correct=False,
                brier_score=0.30,
                log_loss=0.80,
            ),
            record(
                favourite_probability=61.0,
                confidence=50.0,
                correct=True,
                brier_score=0.15,
                log_loss=0.50,
            ),
        )

        segment = self.service._numeric_segment(
            records,
            dimension="favourite_probability",
            lower=50,
            upper=55,
            value_getter=lambda item:
                item.favourite_probability,
        )

        self.assertEqual(
            segment.segment,
            "50-55",
        )
        self.assertEqual(
            segment.predictions,
            2,
        )
        self.assertEqual(
            segment.correct,
            1,
        )
        self.assertEqual(
            segment.accuracy,
            50.0,
        )
        self.assertEqual(
            segment.average_brier_score,
            0.25,
        )
        self.assertEqual(
            segment.average_log_loss,
            0.7,
        )

    def test_empty_numeric_segment_is_safe(self):
        segment = self.service._numeric_segment(
            (),
            dimension="confidence",
            lower=80,
            upper=101,
            value_getter=lambda item:
                item.confidence,
        )

        self.assertEqual(
            segment.predictions,
            0,
        )
        self.assertIsNone(
            segment.accuracy,
        )
        self.assertIsNone(
            segment.average_brier_score,
        )
        self.assertIsNone(
            segment.average_log_loss,
        )

    def test_upper_probability_band_is_labelled_100(self):
        segment = self.service._numeric_segment(
            (
                record(
                    favourite_probability=90.0,
                    confidence=90.0,
                    correct=True,
                    brier_score=0.01,
                    log_loss=0.10,
                ),
            ),
            dimension="favourite_probability",
            lower=80,
            upper=101,
            value_getter=lambda item:
                item.favourite_probability,
        )

        self.assertEqual(
            segment.segment,
            "80-100",
        )

    def test_categorical_segments_are_largest_first(self):
        records = (
            record(
                favourite_probability=60,
                confidence=60,
                correct=True,
                brier_score=0.2,
                log_loss=0.6,
                stage="Group A",
            ),
            record(
                favourite_probability=60,
                confidence=60,
                correct=False,
                brier_score=0.3,
                log_loss=0.8,
                stage="Group A",
            ),
            record(
                favourite_probability=60,
                confidence=60,
                correct=True,
                brier_score=0.2,
                log_loss=0.6,
                stage="Final",
            ),
        )

        segments = (
            self.service._categorical_segments(
                records,
                dimension="stage",
                value_getter=lambda item:
                    item.stage,
            )
        )

        self.assertEqual(
            segments[0].segment,
            "Group A",
        )
        self.assertEqual(
            segments[0].predictions,
            2,
        )
        self.assertEqual(
            segments[1].segment,
            "Final",
        )

    def test_unknown_category_can_be_grouped(self):
        records = (
            record(
                favourite_probability=60,
                confidence=60,
                correct=True,
                brier_score=0.2,
                log_loss=0.6,
                tournament=None,
            ),
        )

        segments = (
            self.service._categorical_segments(
                records,
                dimension="tournament",
                value_getter=lambda item:
                    item.tournament
                    or "Unknown",
            )
        )

        self.assertEqual(
            segments[0].segment,
            "Unknown",
        )

    def test_summary_metrics(self):
        records = (
            record(
                favourite_probability=60,
                confidence=60,
                correct=True,
                brier_score=0.20,
                log_loss=0.60,
            ),
            record(
                favourite_probability=60,
                confidence=60,
                correct=True,
                brier_score=0.10,
                log_loss=0.40,
            ),
            record(
                favourite_probability=60,
                confidence=60,
                correct=False,
                brier_score=0.40,
                log_loss=0.90,
            ),
        )

        result = self.service._summarise(
            records,
            dimension="test",
            segment="example",
        )

        self.assertEqual(
            result.predictions,
            3,
        )
        self.assertEqual(
            result.correct,
            2,
        )
        self.assertEqual(
            result.accuracy,
            66.667,
        )
        self.assertEqual(
            result.average_brier_score,
            0.233333,
        )
        self.assertEqual(
            result.average_log_loss,
            0.633333,
        )

    def test_probability_band_boundaries_do_not_overlap(self):
        records = (
            record(
                favourite_probability=55.0,
                confidence=50.0,
                correct=True,
                brier_score=0.2,
                log_loss=0.6,
            ),
        )

        lower = self.service._numeric_segment(
            records,
            dimension="favourite_probability",
            lower=50,
            upper=55,
            value_getter=lambda item:
                item.favourite_probability,
        )

        upper = self.service._numeric_segment(
            records,
            dimension="favourite_probability",
            lower=55,
            upper=60,
            value_getter=lambda item:
                item.favourite_probability,
        )

        self.assertEqual(
            lower.predictions,
            0,
        )
        self.assertEqual(
            upper.predictions,
            1,
        )

    def test_percentage_handles_zero_denominator(self):
        self.assertIsNone(
            self.service._percentage(
                0,
                0,
            )
        )

        self.assertEqual(
            self.service._percentage(
                3,
                4,
            ),
            75.0,
        )


if __name__ == "__main__":
    unittest.main()
