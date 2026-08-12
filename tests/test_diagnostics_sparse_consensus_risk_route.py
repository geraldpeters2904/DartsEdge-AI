import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.routes.diagnostics import (
    sparse_consensus_risk_endpoint,
)


class DiagnosticsSparseConsensusRiskRouteTests(
    unittest.TestCase
):
    @patch(
        "app.routes.diagnostics."
        "CurrentMatchEnrichmentV33SparseConsensusRiskDiagnosticService"
    )
    @patch(
        "app.routes.diagnostics."
        "CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService"
    )
    def test_returns_diagnostic_payload(
        self,
        flag_service_class,
        diagnostic_service_class,
    ):
        flag_service_class._select_match_ids.return_value = list(
            range(2500)
        )

        diagnostic = SimpleNamespace(
            model_version="transparent-v3.3",
            window_size=1000,
            offset=1500,
            segment_matches=140,
            flagged_matches=9,
            density=6.428571,
            risk_state=(
                "HIGH_SPARSE_CONSENSUS_RISK"
            ),
            elevated=True,
            high=True,
            explanation="High-risk test state.",
        )

        (
            diagnostic_service_class
            .return_value
            .analyse
            .return_value
        ) = diagnostic

        result = sparse_consensus_risk_endpoint(
            db=object(),
        )

        self.assertEqual(
            result["model_version"],
            "transparent-v3.3",
        )

        self.assertEqual(
            result["window_size"],
            1000,
        )

        self.assertEqual(
            result["offset"],
            1500,
        )

        self.assertEqual(
            result["segment_matches"],
            140,
        )

        self.assertEqual(
            result["flagged_matches"],
            9,
        )

        self.assertEqual(
            result["density"],
            6.428571,
        )

        self.assertEqual(
            result["risk_state"],
            "HIGH_SPARSE_CONSENSUS_RISK",
        )

        self.assertTrue(
            result["elevated"]
        )

        self.assertTrue(
            result["high"]
        )

    @patch(
        "app.routes.diagnostics."
        "CurrentMatchEnrichmentV33SparseConsensusRiskDiagnosticService"
    )
    @patch(
        "app.routes.diagnostics."
        "CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService"
    )
    def test_uses_most_recent_1000_completed_matches(
        self,
        flag_service_class,
        diagnostic_service_class,
    ):
        flag_service_class._select_match_ids.return_value = list(
            range(17000)
        )

        (
            diagnostic_service_class
            .return_value
            .analyse
            .return_value
        ) = SimpleNamespace(
            model_version="transparent-v3.3",
            window_size=1000,
            offset=16000,
            segment_matches=140,
            flagged_matches=9,
            density=6.428571,
            risk_state=(
                "HIGH_SPARSE_CONSENSUS_RISK"
            ),
            elevated=True,
            high=True,
            explanation="High-risk test state.",
        )

        sparse_consensus_risk_endpoint(
            db=object(),
        )

        (
            diagnostic_service_class
            .return_value
            .analyse
            .assert_called_once_with(
                unittest.mock.ANY,
                offset=16000,
                window_size=1000,
                probability_lower=65.0,
                probability_upper=70.0,
                history_threshold=3,
                agreement_threshold=100.0,
                competition_code="MODUS",
            )
        )

    @patch(
        "app.routes.diagnostics."
        "CurrentMatchEnrichmentV33SparseConsensusRiskDiagnosticService"
    )
    @patch(
        "app.routes.diagnostics."
        "CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService"
    )
    def test_short_history_uses_zero_offset(
        self,
        flag_service_class,
        diagnostic_service_class,
    ):
        flag_service_class._select_match_ids.return_value = list(
            range(600)
        )

        (
            diagnostic_service_class
            .return_value
            .analyse
            .return_value
        ) = SimpleNamespace(
            model_version="transparent-v3.3",
            window_size=1000,
            offset=0,
            segment_matches=90,
            flagged_matches=0,
            density=0.0,
            risk_state="NORMAL",
            elevated=False,
            high=False,
            explanation="Normal test state.",
        )

        sparse_consensus_risk_endpoint(
            db=object(),
        )

        call = (
            diagnostic_service_class
            .return_value
            .analyse
            .call_args
        )

        self.assertEqual(
            call.kwargs["offset"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
