import unittest
from types import SimpleNamespace

from app.services.current_match_enrichment_v33_sparse_consensus_risk_diagnostic_service import (
    CurrentMatchEnrichmentV33SparseConsensusRiskDiagnosticService,
)
from app.services.current_match_enrichment_v33_sparse_consensus_risk_state_service import (
    CurrentMatchEnrichmentV33SparseConsensusRiskStateService,
)


class FakeRiskFlagService:
    def __init__(
        self,
        *,
        segment_matches,
        flagged_matches,
    ):
        self.segment_matches = segment_matches
        self.flagged_matches = flagged_matches
        self.calls = []

    def analyse(
        self,
        db,
        **kwargs,
    ):
        self.calls.append(
            kwargs
        )

        return SimpleNamespace(
            model_version="transparent-v3.3",
            segment_matches=self.segment_matches,
            flagged_matches=self.flagged_matches,
        )


class CurrentMatchEnrichmentV33SparseConsensusRiskDiagnosticServiceTests(
    unittest.TestCase
):
    def _service(
        self,
        *,
        segment_matches,
        flagged_matches,
    ):
        fake = FakeRiskFlagService(
            segment_matches=segment_matches,
            flagged_matches=flagged_matches,
        )

        service = (
            CurrentMatchEnrichmentV33SparseConsensusRiskDiagnosticService(
                risk_flag_service=fake,
                risk_state_service=(
                    CurrentMatchEnrichmentV33SparseConsensusRiskStateService()
                ),
            )
        )

        return service, fake

    def test_normal_state(self):
        service, fake = self._service(
            segment_matches=200,
            flagged_matches=2,
        )

        result = service.analyse(
            object(),
            offset=1000,
            window_size=1000,
        )

        self.assertEqual(
            result.density,
            1.0,
        )

        self.assertEqual(
            result.risk_state,
            "NORMAL",
        )

        self.assertFalse(
            result.elevated
        )

        self.assertFalse(
            result.high
        )

        self.assertEqual(
            len(fake.calls),
            1,
        )

    def test_elevated_state(self):
        service, _ = self._service(
            segment_matches=200,
            flagged_matches=3,
        )

        result = service.analyse(
            object(),
            offset=2000,
            window_size=1000,
        )

        self.assertEqual(
            result.density,
            1.5,
        )

        self.assertEqual(
            result.risk_state,
            "ELEVATED_SPARSE_CONSENSUS_RISK",
        )

        self.assertTrue(
            result.elevated
        )

        self.assertFalse(
            result.high
        )

    def test_high_state(self):
        service, _ = self._service(
            segment_matches=100,
            flagged_matches=4,
        )

        result = service.analyse(
            object(),
            offset=3000,
            window_size=1000,
        )

        self.assertEqual(
            result.density,
            4.0,
        )

        self.assertEqual(
            result.risk_state,
            "HIGH_SPARSE_CONSENSUS_RISK",
        )

        self.assertTrue(
            result.elevated
        )

        self.assertTrue(
            result.high
        )

    def test_unknown_when_segment_is_empty(self):
        service, _ = self._service(
            segment_matches=0,
            flagged_matches=0,
        )

        result = service.analyse(
            object(),
            offset=0,
            window_size=1000,
        )

        self.assertIsNone(
            result.density,
        )

        self.assertEqual(
            result.risk_state,
            "UNKNOWN",
        )

    def test_passes_configuration_to_flag_service(self):
        service, fake = self._service(
            segment_matches=100,
            flagged_matches=2,
        )

        service.analyse(
            object(),
            offset=5000,
            window_size=750,
            probability_lower=64.0,
            probability_upper=71.0,
            history_threshold=4,
            agreement_threshold=95.0,
            competition_code="MODUS",
        )

        call = fake.calls[0]

        self.assertEqual(
            call["offset"],
            5000,
        )

        self.assertEqual(
            call["limit"],
            750,
        )

        self.assertEqual(
            call["probability_lower"],
            64.0,
        )

        self.assertEqual(
            call["probability_upper"],
            71.0,
        )

        self.assertEqual(
            call["history_threshold"],
            4,
        )

        self.assertEqual(
            call["agreement_threshold"],
            95.0,
        )

    def test_rejects_negative_offset(self):
        service, _ = self._service(
            segment_matches=100,
            flagged_matches=1,
        )

        with self.assertRaisesRegex(
            ValueError,
            "offset cannot be negative",
        ):
            service.analyse(
                object(),
                offset=-1,
            )

    def test_rejects_invalid_window_size(self):
        service, _ = self._service(
            segment_matches=100,
            flagged_matches=1,
        )

        with self.assertRaisesRegex(
            ValueError,
            "greater than zero",
        ):
            service.analyse(
                object(),
                offset=0,
                window_size=0,
            )


if __name__ == "__main__":
    unittest.main()
