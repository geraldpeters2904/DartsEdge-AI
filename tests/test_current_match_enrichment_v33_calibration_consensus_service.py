import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_calibration_consensus_service import (
    CurrentMatchEnrichmentV33CalibrationConsensusService,
)


class FakeEvidenceService:
    def __init__(self, reports):
        self.reports = list(reports)
        self.calls = []

    def analyse(self, db, **kwargs):
        self.calls.append(kwargs)
        return self.reports.pop(0)


def evidence(
    *,
    training_offset,
    validation_offset,
    shrink,
    accepted,
    baseline_accuracy=60.0,
    candidate_accuracy=60.0,
    baseline_brier=0.24,
    candidate_brier=0.23,
    baseline_logloss=0.67,
    candidate_logloss=0.65,
):
    return SimpleNamespace(
        model_version="transparent-v3.3",
        training_offset=training_offset,
        validation_offset=validation_offset,
        recommended_shrink_fraction=shrink,
        recommendation_accepted=accepted,
        validation_baseline=SimpleNamespace(
            accuracy=baseline_accuracy,
            brier_score=baseline_brier,
            log_loss=baseline_logloss,
        ),
        validation_candidate=SimpleNamespace(
            accuracy=candidate_accuracy,
            brier_score=candidate_brier,
            log_loss=candidate_logloss,
        ),
    )


class CurrentMatchEnrichmentV33CalibrationConsensusServiceTests(
    unittest.TestCase
):
    def test_three_of_four_supports_calibration(self):
        reports = (
            evidence(
                training_offset=1,
                validation_offset=2,
                shrink=0.0,
                accepted=False,
            ),
            evidence(
                training_offset=2,
                validation_offset=3,
                shrink=0.3,
                accepted=True,
            ),
            evidence(
                training_offset=3,
                validation_offset=4,
                shrink=0.4,
                accepted=True,
            ),
            evidence(
                training_offset=4,
                validation_offset=5,
                shrink=0.4,
                accepted=True,
            ),
        )

        service = (
            CurrentMatchEnrichmentV33CalibrationConsensusService(
                evidence_service=FakeEvidenceService(
                    reports
                )
            )
        )

        result = service.analyse(
            object(),
            candidate_shrink_fractions=(
                0.0,
                0.1,
                0.2,
                0.3,
                0.4,
            ),
            training_offsets=(1, 2, 3, 4),
            validation_offsets=(2, 3, 4, 5),
            minimum_calibration_support=0.67,
            minimum_exact_consensus=0.67,
            minimum_splits=3,
        )

        self.assertTrue(
            result.calibration_supported
        )

        self.assertEqual(
            result.accepted_splits,
            3,
        )

        self.assertEqual(
            result.accepted_percentage,
            75.0,
        )

    def test_two_of_four_exact_votes_do_not_promote(self):
        reports = (
            evidence(
                training_offset=1,
                validation_offset=2,
                shrink=0.0,
                accepted=False,
            ),
            evidence(
                training_offset=2,
                validation_offset=3,
                shrink=0.3,
                accepted=True,
            ),
            evidence(
                training_offset=3,
                validation_offset=4,
                shrink=0.4,
                accepted=True,
            ),
            evidence(
                training_offset=4,
                validation_offset=5,
                shrink=0.4,
                accepted=True,
            ),
        )

        service = (
            CurrentMatchEnrichmentV33CalibrationConsensusService(
                evidence_service=FakeEvidenceService(
                    reports
                )
            )
        )

        result = service.analyse(
            object(),
            candidate_shrink_fractions=(
                0.0,
                0.1,
                0.2,
                0.3,
                0.4,
            ),
            training_offsets=(1, 2, 3, 4),
            validation_offsets=(2, 3, 4, 5),
            minimum_calibration_support=0.67,
            minimum_exact_consensus=0.67,
        )

        self.assertEqual(
            result.consensus_shrink_fraction,
            0.4,
        )

        self.assertEqual(
            result.consensus_votes,
            2,
        )

        self.assertEqual(
            result.consensus_percentage,
            50.0,
        )

        self.assertFalse(
            result.exact_shrink_promotion_recommended
        )

    def test_exact_consensus_can_promote(self):
        reports = (
            evidence(
                training_offset=1,
                validation_offset=2,
                shrink=0.4,
                accepted=True,
            ),
            evidence(
                training_offset=2,
                validation_offset=3,
                shrink=0.4,
                accepted=True,
            ),
            evidence(
                training_offset=3,
                validation_offset=4,
                shrink=0.4,
                accepted=True,
            ),
        )

        service = (
            CurrentMatchEnrichmentV33CalibrationConsensusService(
                evidence_service=FakeEvidenceService(
                    reports
                )
            )
        )

        result = service.analyse(
            object(),
            candidate_shrink_fractions=(
                0.0,
                0.4,
            ),
            training_offsets=(1, 2, 3),
            validation_offsets=(2, 3, 4),
            minimum_calibration_support=0.67,
            minimum_exact_consensus=0.67,
        )

        self.assertTrue(
            result.calibration_supported
        )

        self.assertTrue(
            result.exact_shrink_promotion_recommended
        )

        self.assertEqual(
            result.consensus_shrink_fraction,
            0.4,
        )

    def test_insufficient_split_count_blocks_support(self):
        reports = (
            evidence(
                training_offset=1,
                validation_offset=2,
                shrink=0.4,
                accepted=True,
            ),
            evidence(
                training_offset=2,
                validation_offset=3,
                shrink=0.4,
                accepted=True,
            ),
        )

        service = (
            CurrentMatchEnrichmentV33CalibrationConsensusService(
                evidence_service=FakeEvidenceService(
                    reports
                )
            )
        )

        result = service.analyse(
            object(),
            candidate_shrink_fractions=(
                0.0,
                0.4,
            ),
            training_offsets=(1, 2),
            validation_offsets=(2, 3),
            minimum_splits=3,
        )

        self.assertFalse(
            result.calibration_supported
        )

    def test_split_summary_metric_directions(self):
        report = evidence(
            training_offset=10,
            validation_offset=20,
            shrink=0.4,
            accepted=True,
            baseline_accuracy=60.0,
            candidate_accuracy=60.5,
            baseline_brier=0.24,
            candidate_brier=0.23,
            baseline_logloss=0.67,
            candidate_logloss=0.65,
        )

        summary = (
            CurrentMatchEnrichmentV33CalibrationConsensusService
            ._summarise_split(report)
        )

        self.assertEqual(
            summary.accuracy_change,
            0.5,
        )

        self.assertEqual(
            summary.brier_gain,
            0.01,
        )

        self.assertEqual(
            summary.log_loss_gain,
            0.02,
        )

    def test_requires_equal_offset_lengths(self):
        service = (
            CurrentMatchEnrichmentV33CalibrationConsensusService(
                evidence_service=FakeEvidenceService(
                    ()
                )
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "equal lengths",
        ):
            service.analyse(
                object(),
                candidate_shrink_fractions=(
                    0.0,
                    0.4,
                ),
                training_offsets=(1, 2),
                validation_offsets=(2,),
            )

    def test_requires_valid_support_threshold(self):
        service = (
            CurrentMatchEnrichmentV33CalibrationConsensusService(
                evidence_service=FakeEvidenceService(
                    ()
                )
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "minimum_calibration_support",
        ):
            service.analyse(
                object(),
                candidate_shrink_fractions=(
                    0.0,
                    0.4,
                ),
                training_offsets=(1,),
                validation_offsets=(2,),
                minimum_calibration_support=0.0,
            )

    def test_difference_handles_missing_values(self):
        self.assertIsNone(
            CurrentMatchEnrichmentV33CalibrationConsensusService
            ._difference(
                None,
                1.0,
            )
        )

        self.assertEqual(
            CurrentMatchEnrichmentV33CalibrationConsensusService
            ._difference(
                2.0,
                1.25,
            ),
            0.75,
        )


if __name__ == "__main__":
    unittest.main()
