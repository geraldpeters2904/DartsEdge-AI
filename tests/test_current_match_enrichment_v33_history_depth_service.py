import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_history_depth_service import (
    CurrentMatchEnrichmentV33HistoryDepthService,
    _HistoryDepthRecord,
)


class CurrentMatchEnrichmentV33HistoryDepthServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33HistoryDepthService()
        )

    def test_minimum_history_segment(self):
        records = (
            _HistoryDepthRecord(
                correct=True,
                brier_score=0.20,
                log_loss=0.60,
                minimum_history=3,
                combined_history=12,
            ),
            _HistoryDepthRecord(
                correct=False,
                brier_score=0.30,
                log_loss=0.80,
                minimum_history=4,
                combined_history=20,
            ),
            _HistoryDepthRecord(
                correct=True,
                brier_score=0.15,
                log_loss=0.50,
                minimum_history=7,
                combined_history=25,
            ),
        )

        segment = self.service._segment(
            records,
            dimension="minimum_history",
            lower=0,
            upper=5,
            value_getter=lambda item:
                item.minimum_history,
        )

        self.assertEqual(
            segment.segment,
            "0-4",
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

    def test_open_ended_history_segment(self):
        records = (
            _HistoryDepthRecord(
                correct=True,
                brier_score=0.10,
                log_loss=0.40,
                minimum_history=45,
                combined_history=90,
            ),
        )

        segment = self.service._segment(
            records,
            dimension="minimum_history",
            lower=40,
            upper=None,
            value_getter=lambda item:
                item.minimum_history,
        )

        self.assertEqual(
            segment.segment,
            "40+",
        )
        self.assertEqual(
            segment.predictions,
            1,
        )
        self.assertEqual(
            segment.accuracy,
            100.0,
        )

    def test_empty_segment_is_safe(self):
        segment = self.service._segment(
            (),
            dimension="combined_history",
            lower=80,
            upper=None,
            value_getter=lambda item:
                item.combined_history,
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

    def test_band_boundaries_do_not_overlap(self):
        records = (
            _HistoryDepthRecord(
                correct=True,
                brier_score=0.20,
                log_loss=0.60,
                minimum_history=5,
                combined_history=10,
            ),
        )

        lower = self.service._segment(
            records,
            dimension="minimum_history",
            lower=0,
            upper=5,
            value_getter=lambda item:
                item.minimum_history,
        )

        upper = self.service._segment(
            records,
            dimension="minimum_history",
            lower=5,
            upper=10,
            value_getter=lambda item:
                item.minimum_history,
        )

        self.assertEqual(
            lower.predictions,
            0,
        )
        self.assertEqual(
            upper.predictions,
            1,
        )

    def test_log_loss_matches_expected_value(self):
        value = self.service._log_loss(
            0.75
        )

        self.assertAlmostEqual(
            value,
            0.287682,
            places=6,
        )

    def test_log_loss_clips_extreme_probability(self):
        value = self.service._log_loss(
            0.0
        )

        self.assertGreater(
            value,
            0.0,
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

    def test_average_ignores_missing_values(self):
        self.assertEqual(
            self.service._average(
                [
                    0.20,
                    None,
                    0.40,
                ]
            ),
            0.30,
        )

        self.assertIsNone(
            self.service._average(
                [
                    None,
                    None,
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()
