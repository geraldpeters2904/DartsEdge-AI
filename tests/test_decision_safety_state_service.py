import unittest

from app.services.decision_safety_state_service import (
    DecisionSafetyStateService,
)


class DecisionSafetyStateServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            DecisionSafetyStateService()
        )

    def test_high_regime_is_high_caution(self):
        result = self.service.classify(
            trust_score=72.0,
            sparse_consensus_risk_state=(
                "HIGH_SPARSE_CONSENSUS_RISK"
            ),
        )

        self.assertEqual(
            result.state,
            self.service.HIGH_CAUTION,
        )
        self.assertTrue(
            result.caution
        )
        self.assertTrue(
            result.high_caution
        )

    def test_elevated_regime_is_caution(self):
        result = self.service.classify(
            trust_score=72.0,
            sparse_consensus_risk_state=(
                "ELEVATED_SPARSE_CONSENSUS_RISK"
            ),
        )

        self.assertEqual(
            result.state,
            self.service.CAUTION,
        )

    def test_low_trust_is_caution(self):
        result = self.service.classify(
            trust_score=50.0,
            sparse_consensus_risk_state="NORMAL",
        )

        self.assertEqual(
            result.state,
            self.service.CAUTION,
        )

    def test_normal_regime_and_good_trust_is_normal(self):
        result = self.service.classify(
            trust_score=72.0,
            sparse_consensus_risk_state="NORMAL",
        )

        self.assertEqual(
            result.state,
            self.service.NORMAL,
        )
        self.assertFalse(
            result.caution
        )

    def test_missing_trust_is_unknown(self):
        result = self.service.classify(
            trust_score=None,
            sparse_consensus_risk_state="NORMAL",
        )

        self.assertEqual(
            result.state,
            self.service.UNKNOWN,
        )

    def test_unknown_regime_is_unknown(self):
        result = self.service.classify(
            trust_score=72.0,
            sparse_consensus_risk_state="UNKNOWN",
        )

        self.assertEqual(
            result.state,
            self.service.UNKNOWN,
        )

    def test_invalid_trust_score_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "between 0 and 100",
        ):
            self.service.classify(
                trust_score=101.0,
                sparse_consensus_risk_state="NORMAL",
            )


if __name__ == "__main__":
    unittest.main()
