import unittest

from app.services.current_match_enrichment_v33_weight_evidence_service import (
    CurrentMatchEnrichmentV33WeightEvidenceService,
    V33WeightCandidateEvidence,
)


class FakeWeightEvidenceService(
    CurrentMatchEnrichmentV33WeightEvidenceService
):
    def __init__(self):
        self.calls = []

    def _evaluate(
        self,
        db,
        *,
        engine,
        weight,
        offset,
        limit,
        competition_code,
    ):
        self.calls.append(
            (
                round(float(weight), 6),
                offset,
                limit,
                competition_code,
                engine.MODEL_VERSION,
            )
        )

        training = offset == 100

        if training:
            values = {
                0.12: (60.0, 0.250, 0.700),
                0.10: (60.0, 0.245, 0.695),
                0.08: (61.0, 0.240, 0.690),
                0.05: (60.0, 0.242, 0.692),
                0.03: (59.0, 0.246, 0.697),
                0.00: (58.0, 0.252, 0.705),
            }
        else:
            values = {
                0.12: (62.0, 0.248, 0.698),
                0.08: (61.0, 0.238, 0.686),
            }

        accuracy, brier, log_loss = values[
            round(float(weight), 6)
        ]

        return V33WeightCandidateEvidence(
            weight=float(weight),
            accuracy=accuracy,
            brier_score=brier,
            log_loss=log_loss,
        )

    def _matches_evaluated(
        self,
        db,
        *,
        engine,
        offset,
        limit,
        competition_code,
    ):
        return limit


class CurrentMatchEnrichmentV33WeightEvidenceIntegrationTests(
    unittest.TestCase
):
    def test_training_winner_is_checked_on_holdout(self):
        service = FakeWeightEvidenceService()

        report = service.analyse(
            object(),
            feature_name="finishing_strength",
            candidate_weights=(
                0.12,
                0.10,
                0.08,
                0.05,
                0.03,
                0.00,
            ),
            training_offset=100,
            training_limit=100,
            validation_offset=200,
            validation_limit=100,
            competition_code="MODUS",
        )

        self.assertEqual(
            report.model_version,
            "transparent-v3.3",
        )

        self.assertEqual(
            report.current_weight,
            0.12,
        )

        self.assertEqual(
            report.training_winner.weight,
            0.08,
        )

        self.assertEqual(
            report.recommended_weight,
            0.08,
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

        self.assertLess(
            report.validation_candidate.brier_score,
            report.validation_baseline.brier_score,
        )

        self.assertLess(
            report.validation_candidate.log_loss,
            report.validation_baseline.log_loss,
        )

    def test_all_evaluations_use_v33(self):
        service = FakeWeightEvidenceService()

        service.analyse(
            object(),
            feature_name="finishing_strength",
            candidate_weights=(
                0.12,
                0.08,
            ),
            training_offset=100,
            training_limit=100,
            validation_offset=200,
            validation_limit=100,
        )

        self.assertTrue(
            service.calls
        )

        self.assertTrue(
            all(
                call[4] == "transparent-v3.3"
                for call in service.calls
            )
        )

    def test_overlapping_windows_are_rejected_before_evaluation(
        self,
    ):
        service = FakeWeightEvidenceService()

        with self.assertRaisesRegex(
            ValueError,
            "overlap",
        ):
            service.analyse(
                object(),
                feature_name="finishing_strength",
                candidate_weights=(
                    0.12,
                    0.08,
                ),
                training_offset=100,
                training_limit=100,
                validation_offset=150,
                validation_limit=100,
            )

        self.assertEqual(
            service.calls,
            [],
        )


if __name__ == "__main__":
    unittest.main()
