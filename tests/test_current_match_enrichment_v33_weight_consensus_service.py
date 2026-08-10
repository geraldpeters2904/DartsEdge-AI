import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_weight_consensus_service import (
    CurrentMatchEnrichmentV33WeightConsensusService,
)
from app.services.current_match_enrichment_v33_weight_evidence_service import (
    V33WeightCandidateEvidence,
)


def evidence_report(
    *,
    training_offset,
    validation_offset,
    recommended_weight,
    accepted,
    current_weight=0.12,
    baseline_accuracy=60.0,
    candidate_accuracy=60.0,
    baseline_brier=0.25,
    candidate_brier=0.24,
    baseline_log_loss=0.70,
    candidate_log_loss=0.69,
):
    return SimpleNamespace(
        model_version="transparent-v3.3",
        feature_name="finishing_strength",
        current_weight=current_weight,
        training_offset=training_offset,
        validation_offset=validation_offset,
        recommended_weight=recommended_weight,
        recommendation_accepted=accepted,
        validation_baseline=V33WeightCandidateEvidence(
            weight=current_weight,
            accuracy=baseline_accuracy,
            brier_score=baseline_brier,
            log_loss=baseline_log_loss,
        ),
        validation_candidate=V33WeightCandidateEvidence(
            weight=recommended_weight,
            accuracy=candidate_accuracy,
            brier_score=candidate_brier,
            log_loss=candidate_log_loss,
        ),
    )


class FakeWeightEvidenceService:
    def __init__(self, reports):
        self.reports = list(reports)
        self.calls = []

    def analyse(
        self,
        db,
        *,
        feature_name,
        candidate_weights,
        training_offset,
        training_limit,
        validation_offset,
        validation_limit,
        competition_code,
    ):
        self.calls.append(
            (
                feature_name,
                tuple(candidate_weights),
                training_offset,
                training_limit,
                validation_offset,
                validation_limit,
                competition_code,
            )
        )

        return self.reports.pop(0)


class CurrentMatchEnrichmentV33WeightConsensusServiceTests(
    unittest.TestCase
):
    def test_consensus_recommends_repeated_holdout_winner(self):
        fake = FakeWeightEvidenceService(
            [
                evidence_report(
                    training_offset=100,
                    validation_offset=200,
                    recommended_weight=0.08,
                    accepted=True,
                ),
                evidence_report(
                    training_offset=300,
                    validation_offset=400,
                    recommended_weight=0.08,
                    accepted=True,
                ),
                evidence_report(
                    training_offset=500,
                    validation_offset=600,
                    recommended_weight=0.12,
                    accepted=False,
                ),
            ]
        )

        service = (
            CurrentMatchEnrichmentV33WeightConsensusService(
                weight_evidence_service=fake,
            )
        )

        report = service.analyse(
            object(),
            feature_name="finishing_strength",
            candidate_weights=(
                0.12,
                0.08,
                0.05,
            ),
            training_offsets=(
                100,
                300,
                500,
            ),
            validation_offsets=(
                200,
                400,
                600,
            ),
            training_limit=100,
            validation_limit=100,
            minimum_consensus=0.67,
        )

        self.assertEqual(
            report.model_version,
            "transparent-v3.3",
        )
        self.assertEqual(
            report.consensus_weight,
            0.08,
        )
        self.assertEqual(
            report.consensus_votes,
            2,
        )
        self.assertEqual(
            report.consensus_percentage,
            66.667,
        )
        self.assertFalse(
            report.promotion_recommended
        )

        # 2/3 = 0.666..., which is below 0.67.
        self.assertIn(
            "below the required consensus",
            report.reason,
        )

    def test_two_thirds_can_pass_lower_threshold(self):
        fake = FakeWeightEvidenceService(
            [
                evidence_report(
                    training_offset=100,
                    validation_offset=200,
                    recommended_weight=0.08,
                    accepted=True,
                ),
                evidence_report(
                    training_offset=300,
                    validation_offset=400,
                    recommended_weight=0.08,
                    accepted=True,
                ),
                evidence_report(
                    training_offset=500,
                    validation_offset=600,
                    recommended_weight=0.12,
                    accepted=False,
                ),
            ]
        )

        service = (
            CurrentMatchEnrichmentV33WeightConsensusService(
                weight_evidence_service=fake,
            )
        )

        report = service.analyse(
            object(),
            feature_name="finishing_strength",
            candidate_weights=(0.12, 0.08),
            training_offsets=(100, 300, 500),
            validation_offsets=(200, 400, 600),
            minimum_consensus=0.66,
        )

        self.assertTrue(
            report.promotion_recommended
        )

    def test_no_accepted_alternative_gives_no_consensus(self):
        fake = FakeWeightEvidenceService(
            [
                evidence_report(
                    training_offset=100,
                    validation_offset=200,
                    recommended_weight=0.12,
                    accepted=False,
                ),
                evidence_report(
                    training_offset=300,
                    validation_offset=400,
                    recommended_weight=0.12,
                    accepted=False,
                ),
            ]
        )

        service = (
            CurrentMatchEnrichmentV33WeightConsensusService(
                weight_evidence_service=fake,
            )
        )

        report = service.analyse(
            object(),
            feature_name="finishing_strength",
            candidate_weights=(0.12, 0.08),
            training_offsets=(100, 300),
            validation_offsets=(200, 400),
        )

        self.assertIsNone(
            report.consensus_weight
        )
        self.assertEqual(
            report.consensus_votes,
            0,
        )
        self.assertFalse(
            report.promotion_recommended
        )

    def test_split_summary_reports_holdout_changes(self):
        report = evidence_report(
            training_offset=100,
            validation_offset=200,
            recommended_weight=0.08,
            accepted=True,
            baseline_accuracy=60.0,
            candidate_accuracy=61.0,
            baseline_brier=0.25,
            candidate_brier=0.24,
            baseline_log_loss=0.70,
            candidate_log_loss=0.68,
        )

        split = (
            CurrentMatchEnrichmentV33WeightConsensusService
            ._summarise_split(report)
        )

        self.assertEqual(
            split.validation_accuracy_change,
            1.0,
        )
        self.assertEqual(
            split.validation_brier_change,
            0.01,
        )
        self.assertEqual(
            split.validation_log_loss_change,
            0.02,
        )

    def test_requires_matching_split_counts(self):
        service = (
            CurrentMatchEnrichmentV33WeightConsensusService(
                weight_evidence_service=FakeWeightEvidenceService(
                    []
                )
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "equal lengths",
        ):
            service.analyse(
                object(),
                feature_name="finishing_strength",
                candidate_weights=(0.12, 0.08),
                training_offsets=(100, 300),
                validation_offsets=(200,),
            )

    def test_requires_valid_consensus_threshold(self):
        service = (
            CurrentMatchEnrichmentV33WeightConsensusService(
                weight_evidence_service=FakeWeightEvidenceService(
                    []
                )
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "minimum_consensus",
        ):
            service.analyse(
                object(),
                feature_name="finishing_strength",
                candidate_weights=(0.12, 0.08),
                training_offsets=(100,),
                validation_offsets=(200,),
                minimum_consensus=0.0,
            )

    def test_difference_handles_missing_values(self):
        self.assertIsNone(
            CurrentMatchEnrichmentV33WeightConsensusService
            ._difference(
                None,
                0.2,
            )
        )

        self.assertEqual(
            CurrentMatchEnrichmentV33WeightConsensusService
            ._difference(
                0.25,
                0.20,
            ),
            0.05,
        )


if __name__ == "__main__":
    unittest.main()
