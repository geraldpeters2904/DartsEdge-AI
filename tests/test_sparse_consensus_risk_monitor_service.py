import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.sparse_consensus_risk_monitor_service import (
    SparseConsensusRiskMonitor,
)


class SparseConsensusRiskMonitorTests(
    unittest.TestCase
):
    def setUp(self):
        self.monitor = SparseConsensusRiskMonitor(
            interval_seconds=300,
            initial_delay_seconds=0,
            window_size=1000,
        )

    @patch(
        "app.services.sparse_consensus_risk_monitor_service."
        "CurrentMatchEnrichmentV33SparseConsensusRiskDiagnosticService"
    )
    @patch(
        "app.services.sparse_consensus_risk_monitor_service."
        "CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService."
        "_select_match_ids"
    )
    @patch(
        "app.services.sparse_consensus_risk_monitor_service."
        "SessionLocal"
    )
    def test_run_once_stores_latest_regime(
        self,
        session_local,
        select_ids,
        diagnostic_class,
    ):
        db = MagicMock()
        session_local.return_value = db

        select_ids.return_value = list(
            range(17000)
        )

        report = SimpleNamespace(
            density=5.921053,
            risk_state=(
                "HIGH_SPARSE_CONSENSUS_RISK"
            ),
            elevated=True,
            high=True,
            segment_matches=152,
            flagged_matches=9,
        )

        diagnostic = MagicMock()
        diagnostic.analyse.return_value = report
        diagnostic_class.return_value = diagnostic

        status = self.monitor.run_once()

        self.assertEqual(
            status.runs,
            1,
        )
        self.assertEqual(
            status.failures,
            0,
        )
        self.assertEqual(
            status.density,
            5.921053,
        )
        self.assertEqual(
            status.risk_state,
            "HIGH_SPARSE_CONSENSUS_RISK",
        )
        self.assertTrue(
            status.high
        )
        self.assertIs(
            self.monitor.latest_report(),
            report,
        )

        diagnostic.analyse.assert_called_once()

        kwargs = (
            diagnostic.analyse
            .call_args
            .kwargs
        )

        self.assertEqual(
            kwargs["offset"],
            16000,
        )
        self.assertEqual(
            kwargs["window_size"],
            1000,
        )

        db.close.assert_called_once()

    @patch(
        "app.services.sparse_consensus_risk_monitor_service."
        "CurrentMatchEnrichmentV33DualLowHistoryRiskFlagService."
        "_select_match_ids"
    )
    @patch(
        "app.services.sparse_consensus_risk_monitor_service."
        "SessionLocal"
    )
    def test_failure_is_recorded(
        self,
        session_local,
        select_ids,
    ):
        db = MagicMock()
        session_local.return_value = db

        select_ids.side_effect = RuntimeError(
            "boom"
        )

        status = self.monitor.run_once()

        self.assertEqual(
            status.runs,
            1,
        )
        self.assertEqual(
            status.failures,
            1,
        )
        self.assertEqual(
            status.last_error,
            "boom",
        )

        db.close.assert_called_once()

    def test_initial_state_is_unknown(self):
        status = self.monitor.status()

        self.assertFalse(
            status.running
        )
        self.assertEqual(
            status.risk_state,
            "UNKNOWN",
        )
        self.assertIsNone(
            status.density
        )


if __name__ == "__main__":
    unittest.main()
