import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_risk_flag_cross_window_service import (
    CurrentMatchEnrichmentV33RiskFlagCrossWindowService,
)


class FakeRiskFlagService:
    def __init__(self, reports):
        self.reports = list(reports)
        self.calls = []

    def analyse(self, db, **kwargs):
        self.calls.append(kwargs)
        return self.reports.pop(0)


def population(
    *,
    accuracy,
    brier,
    log_loss,
):
    return SimpleNamespace(
        accuracy=accuracy,
        brier_score=brier,
        log_loss=log_loss,
    )


def report(
    *,
    segment_matches,
    flagged_matches,
    filtered_matches,
    coverage_retained,
    full_accuracy,
    flagged_accuracy,
    filtered_accuracy,
    full_brier,
    filtered_brier,
    full_log_loss,
    filtered_log_loss,
):
    return SimpleNamespace(
        segment_matches=segment_matches,
        flagged_matches=flagged_matches,
        filtered_matches=filtered_matches,
        coverage_retained=coverage_retained,
        full_segment=population(
            accuracy=full_accuracy,
            brier=full_brier,
            log_loss=full_log_loss,
        ),
        flagged=population(
            accuracy=flagged_accuracy,
            brier=None,
            log_loss=None,
        ),
        filtered=population(
            accuracy=filtered_accuracy,
            brier=filtered_brier,
            log_loss=filtered_log_loss,
        ),
    )


class CurrentMatchEnrichmentV33RiskFlagCrossWindowServiceTests(
    unittest.TestCase
):
    def test_gain(self):
        self.assertEqual(
            CurrentMatchEnrichmentV33RiskFlagCrossWindowService
            ._gain(
                60.0,
                61.5,
            ),
            1.5,
        )

        self.assertIsNone(
            CurrentMatchEnrichmentV33RiskFlagCrossWindowService
            ._gain(
                None,
                61.5,
            )
        )

    def test_loss_gain(self):
        self.assertEqual(
            CurrentMatchEnrichmentV33RiskFlagCrossWindowService
            ._loss_gain(
                0.24,
                0.23,
            ),
            0.01,
        )

        self.assertIsNone(
            CurrentMatchEnrichmentV33RiskFlagCrossWindowService
            ._loss_gain(
                0.24,
                None,
            )
        )

    def test_analyse_aggregates_windows(self):
        fake = FakeRiskFlagService(
            (
                report(
                    segment_matches=100,
                    flagged_matches=2,
                    filtered_matches=98,
                    coverage_retained=98.0,
                    full_accuracy=60.0,
                    flagged_accuracy=0.0,
                    filtered_accuracy=61.224,
                    full_brier=0.24,
                    filtered_brier=0.235,
                    full_log_loss=0.67,
                    filtered_log_loss=0.66,
                ),
                report(
                    segment_matches=120,
                    flagged_matches=1,
                    filtered_matches=119,
                    coverage_retained=99.167,
                    full_accuracy=62.0,
                    flagged_accuracy=100.0,
                    filtered_accuracy=61.681,
                    full_brier=0.23,
                    filtered_brier=0.231,
                    full_log_loss=0.65,
                    filtered_log_loss=0.651,
                ),
            )
        )

        service = (
            CurrentMatchEnrichmentV33RiskFlagCrossWindowService(
                risk_flag_service=fake,
            )
        )

        result = service.analyse(
            object(),
            offsets=(0, 2000),
            window_size=2000,
        )

        self.assertEqual(
            result.windows_completed,
            2,
        )

        self.assertEqual(
            result.windows_with_flags,
            2,
        )

        self.assertEqual(
            result.accuracy_improved_windows,
            1,
        )

        self.assertEqual(
            result.brier_improved_windows,
            1,
        )

        self.assertEqual(
            result.log_loss_improved_windows,
            1,
        )

        self.assertEqual(
            result.all_metrics_improved_windows,
            1,
        )

        self.assertEqual(
            result.total_segment_matches,
            220,
        )

        self.assertEqual(
            result.total_flagged_matches,
            3,
        )

        self.assertEqual(
            result.total_filtered_matches,
            217,
        )

        self.assertEqual(
            len(fake.calls),
            2,
        )

    def test_requires_offsets(self):
        service = (
            CurrentMatchEnrichmentV33RiskFlagCrossWindowService()
        )

        with self.assertRaisesRegex(
            ValueError,
            "at least one",
        ):
            service.analyse(
                object(),
                offsets=(),
            )

    def test_rejects_invalid_window_size(self):
        service = (
            CurrentMatchEnrichmentV33RiskFlagCrossWindowService()
        )

        with self.assertRaisesRegex(
            ValueError,
            "greater than zero",
        ):
            service.analyse(
                object(),
                offsets=(0,),
                window_size=0,
            )


if __name__ == "__main__":
    unittest.main()
