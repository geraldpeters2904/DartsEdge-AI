import unittest

from app.services.current_match_enrichment_v33_weight_evidence_service import (
    CurrentMatchEnrichmentV33WeightEvidenceService,
    V33WeightCandidateEvidence,
)
from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


class CurrentMatchEnrichmentV33WeightEvidenceServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33WeightEvidenceService()
        )

    def test_engine_weight_change_preserves_v33(self):
        baseline = TransparentPredictionEngineV33()

        candidate = self.service._engine_with_weight(
            baseline,
            "finishing_strength",
            0.05,
        )

        self.assertIsInstance(
            candidate,
            TransparentPredictionEngineV33,
        )

        self.assertEqual(
            candidate.MODEL_VERSION,
            "transparent-v3.3",
        )

        weight = next(
            feature.weight
            for feature in candidate.features
            if feature.name
            == "finishing_strength"
        )

        self.assertEqual(
            weight,
            0.05,
        )

    def test_other_feature_weights_are_unchanged(self):
        baseline = TransparentPredictionEngineV33()

        candidate = self.service._engine_with_weight(
            baseline,
            "finishing_strength",
            0.05,
        )

        baseline_weights = {
            feature.name: feature.weight
            for feature in baseline.features
        }

        candidate_weights = {
            feature.name: feature.weight
            for feature in candidate.features
        }

        for name, weight in baseline_weights.items():
            if name == "finishing_strength":
                continue

            self.assertEqual(
                candidate_weights[name],
                weight,
            )

    def test_windows_overlap_is_detected(self):
        self.assertTrue(
            self.service._windows_overlap(
                100,
                100,
                150,
                100,
            )
        )

        self.assertFalse(
            self.service._windows_overlap(
                100,
                100,
                200,
                100,
            )
        )

    def test_candidate_requires_both_probability_metrics_to_improve(
        self,
    ):
        baseline = V33WeightCandidateEvidence(
            weight=0.12,
            accuracy=60.0,
            brier_score=0.25,
            log_loss=0.70,
        )

        candidate = V33WeightCandidateEvidence(
            weight=0.05,
            accuracy=60.0,
            brier_score=0.24,
            log_loss=0.69,
        )

        accepted, _ = self.service._recommendation(
            current_weight=0.12,
            recommended_weight=0.05,
            baseline=baseline,
            candidate=candidate,
        )

        self.assertTrue(
            accepted
        )

    def test_brier_only_improvement_is_rejected(self):
        baseline = V33WeightCandidateEvidence(
            weight=0.12,
            accuracy=60.0,
            brier_score=0.25,
            log_loss=0.70,
        )

        candidate = V33WeightCandidateEvidence(
            weight=0.05,
            accuracy=60.0,
            brier_score=0.24,
            log_loss=0.71,
        )

        accepted, _ = self.service._recommendation(
            current_weight=0.12,
            recommended_weight=0.05,
            baseline=baseline,
            candidate=candidate,
        )

        self.assertFalse(
            accepted
        )

    def test_material_accuracy_drop_is_rejected(self):
        baseline = V33WeightCandidateEvidence(
            weight=0.12,
            accuracy=60.0,
            brier_score=0.25,
            log_loss=0.70,
        )

        candidate = V33WeightCandidateEvidence(
            weight=0.05,
            accuracy=57.0,
            brier_score=0.24,
            log_loss=0.69,
        )

        accepted, _ = self.service._recommendation(
            current_weight=0.12,
            recommended_weight=0.05,
            baseline=baseline,
            candidate=candidate,
        )

        self.assertFalse(
            accepted
        )

    def test_two_point_accuracy_drop_is_allowed(self):
        baseline = V33WeightCandidateEvidence(
            weight=0.12,
            accuracy=60.0,
            brier_score=0.25,
            log_loss=0.70,
        )

        candidate = V33WeightCandidateEvidence(
            weight=0.05,
            accuracy=58.0,
            brier_score=0.24,
            log_loss=0.69,
        )

        accepted, _ = self.service._recommendation(
            current_weight=0.12,
            recommended_weight=0.05,
            baseline=baseline,
            candidate=candidate,
        )

        self.assertTrue(
            accepted
        )

    def test_current_weight_is_not_recommended_as_change(self):
        baseline = V33WeightCandidateEvidence(
            weight=0.12,
            accuracy=60.0,
            brier_score=0.25,
            log_loss=0.70,
        )

        accepted, reason = self.service._recommendation(
            current_weight=0.12,
            recommended_weight=0.12,
            baseline=baseline,
            candidate=baseline,
        )

        self.assertFalse(
            accepted
        )

        self.assertIn(
            "current v3.3 weight",
            reason,
        )


if __name__ == "__main__":
    unittest.main()
