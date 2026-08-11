import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_sparse_consensus_density_service import (
    CurrentMatchEnrichmentV33SparseConsensusDensityService,
)


class FakeCrossWindowService:
    def __init__(self, report):
        self.report = report

    def analyse(self, db, **kwargs):
        return self.report


def window(
    *,
    offset,
    segment_matches,
    flagged_matches,
    flagged_accuracy,
    accuracy_gain,
    brier_gain,
    log_loss_gain,
):
    return SimpleNamespace(
        offset=offset,
        segment_matches=segment_matches,
        flagged_matches=flagged_matches,
        flagged_accuracy=flagged_accuracy,
        accuracy_gain=accuracy_gain,
        brier_gain=brier_gain,
        log_loss_gain=log_loss_gain,
    )


class CurrentMatchEnrichmentV33SparseConsensusDensityServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33SparseConsensusDensityService()
        )

    def test_density(self):
        self.assertEqual(
            self.service._density(
                2,
                200,
            ),
            1.0,
        )

        self.assertIsNone(
            self.service._density(
                0,
                0,
            )
        )

    def test_density_bands(self):
        self.assertEqual(
            self.service._density_band(0.0),
            "zero",
        )

        self.assertEqual(
            self.service._density_band(0.5),
            "gt0_to_1",
        )

        self.assertEqual(
            self.service._density_band(2.0),
            "gt1_to_3",
        )

        self.assertEqual(
            self.service._density_band(4.0),
            "gt3",
        )

    def test_window_marks_all_metrics_improved(self):
        item = window(
            offset=100,
            segment_matches=100,
            flagged_matches=2,
            flagged_accuracy=0.0,
            accuracy_gain=0.5,
            brier_gain=0.001,
            log_loss_gain=0.002,
        )

        result = self.service._window(
            item
        )

        self.assertEqual(
            result.flagged_density,
            2.0,
        )

        self.assertEqual(
            result.density_band,
            "gt1_to_3",
        )

        self.assertTrue(
            result.all_metrics_improved
        )

    def test_aggregate_band_weighted_flagged_accuracy(self):
        windows = (
            self.service._window(
                window(
                    offset=0,
                    segment_matches=100,
                    flagged_matches=1,
                    flagged_accuracy=100.0,
                    accuracy_gain=-0.1,
                    brier_gain=-0.001,
                    log_loss_gain=-0.002,
                )
            ),
            self.service._window(
                window(
                    offset=100,
                    segment_matches=100,
                    flagged_matches=3,
                    flagged_accuracy=0.0,
                    accuracy_gain=0.5,
                    brier_gain=0.002,
                    log_loss_gain=0.003,
                )
            ),
        )

        result = self.service._aggregate_band(
            "gt0_to_1",
            windows,
        )

        self.assertEqual(
            result.windows,
            1,
        )

    def test_analyse_builds_density_bands(self):
        cross_report = SimpleNamespace(
            model_version="transparent-v3.3",
            windows=(
                window(
                    offset=0,
                    segment_matches=200,
                    flagged_matches=0,
                    flagged_accuracy=None,
                    accuracy_gain=0.0,
                    brier_gain=0.0,
                    log_loss_gain=0.0,
                ),
                window(
                    offset=2000,
                    segment_matches=200,
                    flagged_matches=1,
                    flagged_accuracy=100.0,
                    accuracy_gain=-0.1,
                    brier_gain=-0.001,
                    log_loss_gain=-0.001,
                ),
                window(
                    offset=4000,
                    segment_matches=200,
                    flagged_matches=5,
                    flagged_accuracy=20.0,
                    accuracy_gain=0.7,
                    brier_gain=0.002,
                    log_loss_gain=0.004,
                ),
            ),
        )

        service = (
            CurrentMatchEnrichmentV33SparseConsensusDensityService(
                cross_window_service=FakeCrossWindowService(
                    cross_report
                )
            )
        )

        result = service.analyse(
            object(),
            offsets=(0, 2000, 4000),
            window_size=2000,
        )

        self.assertEqual(
            result.windows_completed,
            3,
        )

        self.assertEqual(
            result.windows_with_flags,
            2,
        )

        band_map = {
            item.band: item
            for item in result.bands
        }

        self.assertEqual(
            band_map["zero"].windows,
            1,
        )

        self.assertEqual(
            band_map["gt0_to_1"].windows,
            1,
        )

        self.assertEqual(
            band_map["gt1_to_3"].windows,
            1,
        )

    def test_average(self):
        self.assertEqual(
            self.service._average(
                (1.0, 2.0, 3.0),
            ),
            2.0,
        )

        self.assertIsNone(
            self.service._average(())
        )


if __name__ == "__main__":
    unittest.main()
