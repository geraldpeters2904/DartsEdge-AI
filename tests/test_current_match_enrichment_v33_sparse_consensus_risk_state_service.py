import unittest

from app.services.current_match_enrichment_v33_sparse_consensus_risk_state_service import (
    CurrentMatchEnrichmentV33SparseConsensusRiskStateService,
)


class CurrentMatchEnrichmentV33SparseConsensusRiskStateServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33SparseConsensusRiskStateService()
        )

    def test_none_density_is_unknown(self):
        result = self.service.classify(
            None
        )

        self.assertEqual(
            result.state,
            self.service.UNKNOWN,
        )

        self.assertFalse(
            result.elevated
        )

        self.assertFalse(
            result.high
        )

    def test_zero_density_is_normal(self):
        result = self.service.classify(
            0.0
        )

        self.assertEqual(
            result.state,
            self.service.NORMAL,
        )

    def test_exactly_one_percent_is_normal(self):
        result = self.service.classify(
            1.0
        )

        self.assertEqual(
            result.state,
            self.service.NORMAL,
        )

        self.assertFalse(
            result.elevated
        )

    def test_just_above_one_percent_is_elevated(self):
        result = self.service.classify(
            1.000001
        )

        self.assertEqual(
            result.state,
            self.service.ELEVATED,
        )

        self.assertTrue(
            result.elevated
        )

        self.assertFalse(
            result.high
        )

    def test_exactly_three_percent_is_elevated(self):
        result = self.service.classify(
            3.0
        )

        self.assertEqual(
            result.state,
            self.service.ELEVATED,
        )

        self.assertTrue(
            result.elevated
        )

        self.assertFalse(
            result.high
        )

    def test_just_above_three_percent_is_high(self):
        result = self.service.classify(
            3.000001
        )

        self.assertEqual(
            result.state,
            self.service.HIGH,
        )

        self.assertTrue(
            result.elevated
        )

        self.assertTrue(
            result.high
        )

    def test_negative_density_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "cannot be negative",
        ):
            self.service.classify(
                -0.1
            )

    def test_classify_counts_calculates_density(self):
        result = self.service.classify_counts(
            flagged_matches=2,
            segment_matches=100,
        )

        self.assertEqual(
            result.density,
            2.0,
        )

        self.assertEqual(
            result.state,
            self.service.ELEVATED,
        )

    def test_zero_segment_is_unknown(self):
        result = self.service.classify_counts(
            flagged_matches=0,
            segment_matches=0,
        )

        self.assertEqual(
            result.state,
            self.service.UNKNOWN,
        )

        self.assertIsNone(
            result.density,
        )

    def test_rejects_flagged_above_segment(self):
        with self.assertRaisesRegex(
            ValueError,
            "cannot exceed",
        ):
            self.service.classify_counts(
                flagged_matches=2,
                segment_matches=1,
            )


if __name__ == "__main__":
    unittest.main()
