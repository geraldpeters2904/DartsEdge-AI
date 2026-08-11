import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_recent_win_rate_history_evidence_service import (
    V33RecentWinRateHistoryCandidateEvidence,
    CurrentMatchEnrichmentV33RecentWinRateHistoryEvidenceService,
)


class CurrentMatchEnrichmentV33RecentWinRateHistoryEvidenceServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33RecentWinRateHistoryEvidenceService()
        )

    def test_ranking_prefers_lower_brier_then_logloss(self):
        better = (
            V33RecentWinRateHistoryCandidateEvidence(
                multiplier=0.5,
                accuracy=60.0,
                brier_score=0.22,
                log_loss=0.64,
            )
        )

        worse = (
            V33RecentWinRateHistoryCandidateEvidence(
                multiplier=1.0,
                accuracy=65.0,
                brier_score=0.23,
                log_loss=0.62,
            )
        )

        self.assertLess(
            better.ranking_key(),
            worse.ranking_key(),
        )

    def test_recommendation_accepts_probability_improvement(self):
        baseline = SimpleNamespace(
            accuracy=60.0,
            brier_score=0.24,
            log_loss=0.67,
        )

        candidate = SimpleNamespace(
            accuracy=59.0,
            brier_score=0.23,
            log_loss=0.65,
        )

        accepted, reason = (
            self.service._recommendation(
                recommended_multiplier=0.5,
                baseline=baseline,
                candidate=candidate,
            )
        )

        self.assertTrue(
            accepted
        )

        self.assertIn(
            "improved both",
            reason,
        )

    def test_recommendation_rejects_accuracy_drop_over_two_points(self):
        baseline = SimpleNamespace(
            accuracy=60.0,
            brier_score=0.24,
            log_loss=0.67,
        )

        candidate = SimpleNamespace(
            accuracy=57.9,
            brier_score=0.23,
            log_loss=0.65,
        )

        accepted, _ = (
            self.service._recommendation(
                recommended_multiplier=0.5,
                baseline=baseline,
                candidate=candidate,
            )
        )

        self.assertFalse(
            accepted
        )

    def test_recommendation_rejects_unchanged_baseline(self):
        baseline = SimpleNamespace(
            accuracy=60.0,
            brier_score=0.24,
            log_loss=0.67,
        )

        accepted, reason = (
            self.service._recommendation(
                recommended_multiplier=1.0,
                baseline=baseline,
                candidate=baseline,
            )
        )

        self.assertFalse(
            accepted
        )

        self.assertIn(
            "Unchanged v3.3",
            reason,
        )

    def test_windows_overlap(self):
        self.assertTrue(
            self.service._windows_overlap(
                100,
                500,
                400,
                500,
            )
        )

        self.assertFalse(
            self.service._windows_overlap(
                100,
                500,
                600,
                500,
            )
        )

    def test_rejects_missing_baseline_candidate(self):
        with self.assertRaisesRegex(
            ValueError,
            "include 1.0",
        ):
            self.service.analyse(
                object(),
                candidate_multipliers=(
                    0.0,
                    0.5,
                ),
                training_offset=100,
                training_limit=500,
                validation_offset=600,
                validation_limit=500,
            )

    def test_rejects_invalid_multiplier(self):
        with self.assertRaisesRegex(
            ValueError,
            "between 0 and 1",
        ):
            self.service.analyse(
                object(),
                candidate_multipliers=(
                    1.0,
                    1.1,
                ),
                training_offset=100,
                training_limit=500,
                validation_offset=600,
                validation_limit=500,
            )

    def test_rejects_overlapping_windows(self):
        with self.assertRaisesRegex(
            ValueError,
            "overlap",
        ):
            self.service.analyse(
                object(),
                candidate_multipliers=(
                    0.5,
                    1.0,
                ),
                training_offset=100,
                training_limit=500,
                validation_offset=400,
                validation_limit=500,
            )


if __name__ == "__main__":
    unittest.main()
