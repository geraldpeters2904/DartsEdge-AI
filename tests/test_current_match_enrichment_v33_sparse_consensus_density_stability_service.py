import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_sparse_consensus_density_stability_service import (
    CurrentMatchEnrichmentV33SparseConsensusDensityStabilityService,
)


def band(
    *,
    name,
    windows,
    flagged_matches,
    flagged_accuracy,
    all_metrics_improved_windows,
    accuracy_gain,
    brier_gain,
    log_loss_gain,
):
    return SimpleNamespace(
        band=name,
        windows=windows,
        flagged_matches=flagged_matches,
        average_flagged_accuracy=flagged_accuracy,
        all_metrics_improved_windows=(
            all_metrics_improved_windows
        ),
        average_accuracy_gain=accuracy_gain,
        average_brier_gain=brier_gain,
        average_log_loss_gain=log_loss_gain,
    )


class FakeDensityService:
    def __init__(self, reports):
        self.reports = list(reports)
        self.calls = []

    def analyse(self, db, **kwargs):
        self.calls.append(kwargs)
        return self.reports.pop(0)


class CurrentMatchEnrichmentV33SparseConsensusDensityStabilityServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33SparseConsensusDensityStabilityService()
        )

    def test_scale_band_positive_when_all_gains_positive(self):
        source = band(
            name="gt1_to_3",
            windows=3,
            flagged_matches=7,
            flagged_accuracy=14.286,
            all_metrics_improved_windows=3,
            accuracy_gain=0.679,
            brier_gain=0.0025,
            log_loss_gain=0.0053,
        )

        result = self.service._scale_band(
            1000,
            source,
        )

        self.assertTrue(
            result.positive_all_metrics
        )

    def test_scale_band_rejects_negative_metric(self):
        source = band(
            name="gt0_to_1",
            windows=3,
            flagged_matches=3,
            flagged_accuracy=100.0,
            all_metrics_improved_windows=0,
            accuracy_gain=-0.2,
            brier_gain=-0.001,
            log_loss_gain=-0.002,
        )

        result = self.service._scale_band(
            1000,
            source,
        )

        self.assertFalse(
            result.positive_all_metrics
        )

    def test_build_band_stable_when_all_active_scales_positive(self):
        reports = (
            (
                1000,
                SimpleNamespace(
                    bands=(
                        band(
                            name="gt1_to_3",
                            windows=3,
                            flagged_matches=7,
                            flagged_accuracy=14.286,
                            all_metrics_improved_windows=3,
                            accuracy_gain=0.679,
                            brier_gain=0.0025,
                            log_loss_gain=0.0053,
                        ),
                    ),
                ),
            ),
            (
                2000,
                SimpleNamespace(
                    bands=(
                        band(
                            name="gt1_to_3",
                            windows=1,
                            flagged_matches=5,
                            flagged_accuracy=20.0,
                            all_metrics_improved_windows=1,
                            accuracy_gain=0.67,
                            brier_gain=0.00245,
                            log_loss_gain=0.00514,
                        ),
                    ),
                ),
            ),
        )

        result = self.service._build_band(
            "gt1_to_3",
            reports,
        )

        self.assertEqual(
            result.positive_scales,
            2,
        )

        self.assertTrue(
            result.stable_positive
        )

    def test_build_band_not_stable_when_one_scale_negative(self):
        reports = (
            (
                1000,
                SimpleNamespace(
                    bands=(
                        band(
                            name="gt0_to_1",
                            windows=3,
                            flagged_matches=3,
                            flagged_accuracy=100.0,
                            all_metrics_improved_windows=0,
                            accuracy_gain=-0.2,
                            brier_gain=-0.001,
                            log_loss_gain=-0.002,
                        ),
                    ),
                ),
            ),
            (
                2000,
                SimpleNamespace(
                    bands=(
                        band(
                            name="gt0_to_1",
                            windows=4,
                            flagged_matches=5,
                            flagged_accuracy=60.0,
                            all_metrics_improved_windows=1,
                            accuracy_gain=0.015,
                            brier_gain=0.0001,
                            log_loss_gain=0.0002,
                        ),
                    ),
                ),
            ),
        )

        result = self.service._build_band(
            "gt0_to_1",
            reports,
        )

        self.assertFalse(
            result.stable_positive
        )

    def test_analyse_marks_above_one_percent_stable(self):
        report_1000 = SimpleNamespace(
            bands=(
                band(
                    name="gt0_to_1",
                    windows=3,
                    flagged_matches=3,
                    flagged_accuracy=100.0,
                    all_metrics_improved_windows=0,
                    accuracy_gain=-0.2,
                    brier_gain=-0.001,
                    log_loss_gain=-0.002,
                ),
                band(
                    name="gt1_to_3",
                    windows=3,
                    flagged_matches=7,
                    flagged_accuracy=14.286,
                    all_metrics_improved_windows=3,
                    accuracy_gain=0.679,
                    brier_gain=0.0025,
                    log_loss_gain=0.0053,
                ),
                band(
                    name="gt3",
                    windows=1,
                    flagged_matches=9,
                    flagged_accuracy=33.333,
                    all_metrics_improved_windows=1,
                    accuracy_gain=1.783,
                    brier_gain=0.0062,
                    log_loss_gain=0.013,
                ),
            ),
        )

        report_2000 = SimpleNamespace(
            bands=(
                band(
                    name="gt0_to_1",
                    windows=4,
                    flagged_matches=5,
                    flagged_accuracy=60.0,
                    all_metrics_improved_windows=1,
                    accuracy_gain=0.015,
                    brier_gain=0.0001,
                    log_loss_gain=0.0002,
                ),
                band(
                    name="gt1_to_3",
                    windows=1,
                    flagged_matches=5,
                    flagged_accuracy=20.0,
                    all_metrics_improved_windows=1,
                    accuracy_gain=0.67,
                    brier_gain=0.00245,
                    log_loss_gain=0.00514,
                ),
                band(
                    name="gt3",
                    windows=1,
                    flagged_matches=10,
                    flagged_accuracy=40.0,
                    all_metrics_improved_windows=1,
                    accuracy_gain=1.229,
                    brier_gain=0.00428,
                    log_loss_gain=0.00895,
                ),
            ),
        )

        service = (
            CurrentMatchEnrichmentV33SparseConsensusDensityStabilityService(
                density_service=FakeDensityService(
                    (
                        report_1000,
                        report_2000,
                    )
                )
            )
        )

        result = service.analyse(
            object(),
            window_sizes=(1000, 2000),
            history_limit=17000,
        )

        self.assertTrue(
            result.above_one_percent_stable
        )

        self.assertEqual(
            result.window_sizes,
            (1000, 2000),
        )

    def test_rejects_empty_window_sizes(self):
        with self.assertRaisesRegex(
            ValueError,
            "at least one",
        ):
            self.service.analyse(
                object(),
                window_sizes=(),
            )

    def test_rejects_invalid_window_size(self):
        with self.assertRaisesRegex(
            ValueError,
            "greater than zero",
        ):
            self.service.analyse(
                object(),
                window_sizes=(1000, 0),
            )


if __name__ == "__main__":
    unittest.main()
