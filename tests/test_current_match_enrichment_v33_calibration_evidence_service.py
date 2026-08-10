import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.current_match_enrichment_v33_calibration_evidence_service import (
    CurrentMatchEnrichmentV33CalibrationEvidenceService,
    V33CalibrationCandidateEvidence,
)


class CurrentMatchEnrichmentV33CalibrationEvidenceServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33CalibrationEvidenceService()
        )

    def test_ranking_prefers_lower_brier_then_logloss(self):
        better = V33CalibrationCandidateEvidence(
            shrink_fraction=0.20,
            accuracy=60.0,
            brier_score=0.23,
            log_loss=0.65,
        )

        worse = V33CalibrationCandidateEvidence(
            shrink_fraction=0.10,
            accuracy=62.0,
            brier_score=0.24,
            log_loss=0.64,
        )

        self.assertLess(
            better.ranking_key(),
            worse.ranking_key(),
        )

    def test_requires_zero_baseline_candidate(self):
        with self.assertRaisesRegex(
            ValueError,
            "must include 0.0",
        ):
            self.service.analyse(
                object(),
                candidate_shrink_fractions=(
                    0.10,
                    0.20,
                ),
                training_offset=0,
                training_limit=100,
                validation_offset=100,
                validation_limit=100,
            )

    def test_rejects_invalid_shrink_fraction(self):
        with self.assertRaisesRegex(
            ValueError,
            "between 0 and 1",
        ):
            self.service.analyse(
                object(),
                candidate_shrink_fractions=(
                    0.0,
                    1.2,
                ),
                training_offset=0,
                training_limit=100,
                validation_offset=100,
                validation_limit=100,
            )

    def test_rejects_overlapping_windows(self):
        with self.assertRaisesRegex(
            ValueError,
            "overlap",
        ):
            self.service.analyse(
                object(),
                candidate_shrink_fractions=(
                    0.0,
                    0.20,
                ),
                training_offset=0,
                training_limit=100,
                validation_offset=50,
                validation_limit=100,
            )

    def test_baseline_training_winner_is_not_accepted(self):
        baseline = V33CalibrationCandidateEvidence(
            shrink_fraction=0.0,
            accuracy=60.0,
            brier_score=0.24,
            log_loss=0.67,
        )

        accepted, reason = (
            self.service._recommendation(
                recommended_shrink_fraction=0.0,
                baseline=baseline,
                candidate=baseline,
            )
        )

        self.assertFalse(
            accepted
        )

        self.assertIn(
            "remained best",
            reason,
        )

    def test_candidate_is_accepted_when_holdout_metrics_improve(self):
        baseline = V33CalibrationCandidateEvidence(
            shrink_fraction=0.0,
            accuracy=60.0,
            brier_score=0.24,
            log_loss=0.67,
        )

        candidate = V33CalibrationCandidateEvidence(
            shrink_fraction=0.20,
            accuracy=59.0,
            brier_score=0.235,
            log_loss=0.66,
        )

        accepted, reason = (
            self.service._recommendation(
                recommended_shrink_fraction=0.20,
                baseline=baseline,
                candidate=candidate,
            )
        )

        self.assertTrue(
            accepted
        )

        self.assertIn(
            "improved",
            reason,
        )

    def test_material_accuracy_loss_is_rejected(self):
        baseline = V33CalibrationCandidateEvidence(
            shrink_fraction=0.0,
            accuracy=60.0,
            brier_score=0.24,
            log_loss=0.67,
        )

        candidate = V33CalibrationCandidateEvidence(
            shrink_fraction=0.20,
            accuracy=57.5,
            brier_score=0.23,
            log_loss=0.65,
        )

        accepted, _reason = (
            self.service._recommendation(
                recommended_shrink_fraction=0.20,
                baseline=baseline,
                candidate=candidate,
            )
        )

        self.assertFalse(
            accepted
        )

    def test_windows_overlap_helper(self):
        self.assertTrue(
            self.service._windows_overlap(
                0,
                100,
                50,
                100,
            )
        )

        self.assertFalse(
            self.service._windows_overlap(
                0,
                100,
                100,
                100,
            )
        )

    @patch(
        "app.services.current_match_enrichment_v33_calibration_evidence_service."
        "CurrentMatchEnrichmentV33CalibrationEvidenceService._matches_evaluated",
        return_value=100,
    )
    @patch(
        "app.services.current_match_enrichment_v33_calibration_evidence_service."
        "CurrentMatchEnrichmentV33CalibrationEvidenceService._evaluate",
    )
    def test_analyse_selects_training_winner_and_validates_it(
        self,
        evaluate,
        matches_evaluated,
    ):
        def fake_evaluate(
            db,
            *,
            shrink_fraction,
            offset,
            limit,
            probability_lower,
            probability_upper,
            minimum_history_upper,
            competition_code,
        ):
            if offset == 0:
                values = {
                    0.0: (60.0, 0.240, 0.670),
                    0.1: (60.0, 0.238, 0.666),
                    0.2: (60.0, 0.235, 0.660),
                }
            else:
                values = {
                    0.0: (61.0, 0.242, 0.672),
                    0.2: (60.5, 0.237, 0.663),
                }

            accuracy, brier, log_loss = values[
                shrink_fraction
            ]

            return V33CalibrationCandidateEvidence(
                shrink_fraction=shrink_fraction,
                accuracy=accuracy,
                brier_score=brier,
                log_loss=log_loss,
            )

        evaluate.side_effect = fake_evaluate

        report = self.service.analyse(
            object(),
            candidate_shrink_fractions=(
                0.0,
                0.10,
                0.20,
            ),
            training_offset=0,
            training_limit=100,
            validation_offset=100,
            validation_limit=100,
        )

        self.assertEqual(
            report.training_winner.shrink_fraction,
            0.20,
        )

        self.assertEqual(
            report.recommended_shrink_fraction,
            0.20,
        )

        self.assertTrue(
            report.recommendation_accepted,
        )

        self.assertEqual(
            report.training_matches_evaluated,
            100,
        )

        self.assertEqual(
            report.validation_matches_evaluated,
            100,
        )


if __name__ == "__main__":
    unittest.main()
