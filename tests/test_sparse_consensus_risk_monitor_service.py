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

    def test_session_creation_failure_is_recorded(self):
        with patch(
            "app.services.sparse_consensus_risk_monitor_service.SessionLocal",
            side_effect=RuntimeError("database unavailable"),
        ):
            monitor = SparseConsensusRiskMonitor(
                interval_seconds=60,
                initial_delay_seconds=0,
            )
            status = monitor.run_once()

        self.assertEqual(status.runs, 1)
        self.assertEqual(status.failures, 1)
        self.assertEqual(
            status.last_message,
            "Sparse-consensus risk refresh failed.",
        )
        self.assertEqual(
            status.last_error,
            "database unavailable",
        )

    def test_stop_waits_for_background_thread_to_exit(self):
        monitor = SparseConsensusRiskMonitor(
            interval_seconds=300,
            initial_delay_seconds=60,
        )

        monitor.start()
        thread = monitor._thread

        self.assertIsNotNone(thread)
        self.assertTrue(thread.is_alive())

        status = monitor.stop()

        self.assertFalse(status.running)
        self.assertFalse(thread.is_alive())

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


    def test_run_once_skips_when_cycle_already_running(self):
        monitor = getattr(self, "monitor", None)
        if monitor is None:
            monitor_class = type(
                self
            ).__module__.split(".")[-1]
            if monitor_class == "test_live_edge_monitor_service":
                monitor = LiveEdgeMonitor(
                    interval_seconds=60,
                    initial_delay_seconds=0,
                )

        acquired = monitor._run_lock.acquire(
            blocking=False
        )
        self.assertTrue(acquired)

        try:
            before = monitor.status()
            status = monitor.run_once()
        finally:
            monitor._run_lock.release()

        self.assertEqual(
            status.runs,
            before.runs,
        )
        self.assertEqual(
            status.failures,
            before.failures,
        )
        self.assertEqual(
            status.last_message,
            before.last_message,
        )
        self.assertEqual(
            status.last_error,
            before.last_error,
        )



if __name__ == "__main__":
    unittest.main()
