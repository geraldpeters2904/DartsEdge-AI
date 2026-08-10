import unittest

from app.services.current_match_enrichment_v33_segment_stability_service import (
    CurrentMatchEnrichmentV33SegmentStabilityService,
    V33SegmentStabilityWindow,
)


class CurrentMatchEnrichmentV33SegmentStabilityServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33SegmentStabilityService()
        )

    def test_weighted_metric_uses_segment_counts(self):
        windows = (
            V33SegmentStabilityWindow(
                offset=100,
                matches_evaluated=500,
                segment_matches=10,
                correct=5,
                accuracy=50.0,
                average_brier_score=0.30,
                average_log_loss=0.80,
            ),
            V33SegmentStabilityWindow(
                offset=600,
                matches_evaluated=500,
                segment_matches=30,
                correct=21,
                accuracy=70.0,
                average_brier_score=0.20,
                average_log_loss=0.60,
            ),
        )

        self.assertEqual(
            self.service._weighted_metric(
                windows,
                "average_brier_score",
            ),
            0.225,
        )

    def test_weighted_metric_ignores_empty_metric(self):
        windows = (
            V33SegmentStabilityWindow(
                offset=100,
                matches_evaluated=500,
                segment_matches=0,
                correct=0,
                accuracy=None,
                average_brier_score=None,
                average_log_loss=None,
            ),
        )

        self.assertIsNone(
            self.service._weighted_metric(
                windows,
                "average_brier_score",
            )
        )

    def test_percentage(self):
        self.assertEqual(
            self.service._percentage(
                3,
                5,
            ),
            60.0,
        )

        self.assertIsNone(
            self.service._percentage(
                0,
                0,
            )
        )

    def test_average(self):
        self.assertEqual(
            self.service._average(
                [
                    0.2,
                    0.4,
                ]
            ),
            0.3,
        )

        self.assertIsNone(
            self.service._average(
                []
            )
        )

    def test_log_loss(self):
        self.assertAlmostEqual(
            self.service._log_loss(
                0.75
            ),
            0.287682,
            places=6,
        )

    def test_rejects_empty_offsets(self):
        with self.assertRaisesRegex(
            ValueError,
            "at least one",
        ):
            self.service.analyse(
                object(),
                offsets=(),
            )

    def test_rejects_invalid_probability_range(self):
        with self.assertRaisesRegex(
            ValueError,
            "must exceed",
        ):
            self.service.analyse(
                object(),
                offsets=(100,),
                probability_lower=70,
                probability_upper=65,
            )

    def test_rejects_invalid_history_range(self):
        with self.assertRaisesRegex(
            ValueError,
            "must exceed",
        ):
            self.service.analyse(
                object(),
                offsets=(100,),
                history_lower=20,
                history_upper=20,
            )


if __name__ == "__main__":
    unittest.main()
