import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_low_history_calibration_service import (
    CurrentMatchEnrichmentV33LowHistoryCalibrationService,
)


class FakeStabilityService:
    def __init__(self):
        self.calls = []

    def analyse(
        self,
        db,
        *,
        offsets,
        window_size,
        probability_lower,
        probability_upper,
        history_lower,
        history_upper,
        competition_code,
    ):
        self.calls.append(
            (
                tuple(offsets),
                window_size,
                probability_lower,
                probability_upper,
                history_lower,
                history_upper,
                competition_code,
            )
        )

        if history_lower == 0:
            return SimpleNamespace(
                model_version="transparent-v3.3",
                weighted_accuracy=57.0,
                weighted_brier_score=0.255,
                weighted_log_loss=0.706,
                total_segment_matches=120,
            )

        return SimpleNamespace(
            model_version="transparent-v3.3",
            weighted_accuracy=68.0,
            weighted_brier_score=0.220,
            weighted_log_loss=0.631,
            total_segment_matches=100,
        )


class CurrentMatchEnrichmentV33LowHistoryCalibrationServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.stability = FakeStabilityService()

        self.service = (
            CurrentMatchEnrichmentV33LowHistoryCalibrationService(
                stability_service=self.stability,
            )
        )

    def test_compares_low_history_with_control(self):
        report = self.service.analyse(
            object(),
            offsets=(100, 600, 1100),
            window_size=500,
            probability_lower=65.0,
            probability_upper=70.0,
            low_history_upper=10,
            control_history_lower=10,
            control_history_upper=20,
            competition_code="MODUS",
        )

        self.assertEqual(
            len(self.stability.calls),
            2,
        )

        self.assertEqual(
            self.stability.calls[0][4:6],
            (0, 10),
        )

        self.assertEqual(
            self.stability.calls[1][4:6],
            (10, 20),
        )

        self.assertEqual(
            report.model_version,
            "transparent-v3.3",
        )

    def test_gap_direction_is_low_history_minus_control(self):
        report = self.service.analyse(
            object(),
            offsets=(100,),
        )

        self.assertEqual(
            report.accuracy_gap,
            -11.0,
        )

        self.assertEqual(
            report.brier_gap,
            0.035,
        )

        self.assertEqual(
            report.log_loss_gap,
            0.075,
        )

    def test_weaker_flags_are_set(self):
        report = self.service.analyse(
            object(),
            offsets=(100,),
        )

        self.assertTrue(
            report.low_history_weaker_accuracy,
        )

        self.assertTrue(
            report.low_history_weaker_brier,
        )

        self.assertTrue(
            report.low_history_weaker_log_loss,
        )

    def test_weakness_requires_minimum_sample(self):
        class SmallSampleService(
            FakeStabilityService
        ):
            def analyse(
                self,
                db,
                *,
                offsets,
                window_size,
                probability_lower,
                probability_upper,
                history_lower,
                history_upper,
                competition_code,
            ):
                result = super().analyse(
                    db,
                    offsets=offsets,
                    window_size=window_size,
                    probability_lower=probability_lower,
                    probability_upper=probability_upper,
                    history_lower=history_lower,
                    history_upper=history_upper,
                    competition_code=competition_code,
                )

                return SimpleNamespace(
                    model_version=result.model_version,
                    weighted_accuracy=result.weighted_accuracy,
                    weighted_brier_score=result.weighted_brier_score,
                    weighted_log_loss=result.weighted_log_loss,
                    total_segment_matches=20,
                )

        service = (
            CurrentMatchEnrichmentV33LowHistoryCalibrationService(
                stability_service=SmallSampleService(),
            )
        )

        report = service.analyse(
            object(),
            offsets=(100,),
        )

        self.assertFalse(
            report.weakness_confirmed,
        )

    def test_weakness_is_confirmed_with_all_metrics_and_samples(self):
        report = self.service.analyse(
            object(),
            offsets=(100, 600),
        )

        self.assertTrue(
            report.weakness_confirmed,
        )

    def test_non_overlapping_control_is_required(self):
        with self.assertRaisesRegex(
            ValueError,
            "cannot overlap",
        ):
            self.service.analyse(
                object(),
                offsets=(100,),
                low_history_upper=10,
                control_history_lower=9,
                control_history_upper=20,
            )

    def test_control_upper_must_exceed_lower(self):
        with self.assertRaisesRegex(
            ValueError,
            "must exceed",
        ):
            self.service.analyse(
                object(),
                offsets=(100,),
                control_history_lower=10,
                control_history_upper=10,
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

    def test_difference_handles_missing_values(self):
        self.assertIsNone(
            self.service._difference(
                None,
                1.0,
            )
        )

        self.assertEqual(
            self.service._difference(
                2.5,
                1.0,
            ),
            1.5,
        )


if __name__ == "__main__":
    unittest.main()
