import unittest
from types import SimpleNamespace

from app.services.live_opportunity_centre_service import (
    _current_sparse_consensus_risk,
)


class FakeQuery:
    def __init__(self, count_value):
        self.count_value = count_value

    def filter(self, *args, **kwargs):
        return self

    def count(self):
        return self.count_value


class FakeDb:
    def __init__(self, count_value):
        self.count_value = count_value

    def query(self, *args, **kwargs):
        return FakeQuery(
            self.count_value
        )


class FakeDiagnosticService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def analyse(self, db, **kwargs):
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return self.result


class LiveOpportunityCentreSparseConsensusRiskTests(
    unittest.TestCase
):
    def test_current_risk_uses_recent_window_offset(self):
        diagnostic = SimpleNamespace(
            density=5.5,
            risk_state="HIGH_SPARSE_CONSENSUS_RISK",
            elevated=True,
            high=True,
            explanation="High-risk regime.",
        )

        service = FakeDiagnosticService(
            result=diagnostic,
        )

        result = _current_sparse_consensus_risk(
            FakeDb(17000),
            diagnostic_service=service,
            window_size=1000,
        )

        self.assertEqual(
            result["density"],
            5.5,
        )

        self.assertEqual(
            result["state"],
            "HIGH_SPARSE_CONSENSUS_RISK",
        )

        self.assertTrue(
            result["elevated"]
        )

        self.assertTrue(
            result["high"]
        )

        self.assertEqual(
            service.calls[0]["offset"],
            16000,
        )

        self.assertEqual(
            service.calls[0]["window_size"],
            1000,
        )

    def test_short_history_uses_zero_offset(self):
        diagnostic = SimpleNamespace(
            density=0.0,
            risk_state="NORMAL",
            elevated=False,
            high=False,
            explanation="Normal regime.",
        )

        service = FakeDiagnosticService(
            result=diagnostic,
        )

        _current_sparse_consensus_risk(
            FakeDb(600),
            diagnostic_service=service,
            window_size=1000,
        )

        self.assertEqual(
            service.calls[0]["offset"],
            0,
        )

    def test_diagnostic_failure_returns_unknown(self):
        service = FakeDiagnosticService(
            error=RuntimeError(
                "diagnostic failed"
            ),
        )

        result = _current_sparse_consensus_risk(
            FakeDb(17000),
            diagnostic_service=service,
            window_size=1000,
        )

        self.assertIsNone(
            result["density"]
        )

        self.assertEqual(
            result["state"],
            "UNKNOWN",
        )

        self.assertFalse(
            result["elevated"]
        )

        self.assertFalse(
            result["high"]
        )

    def test_window_size_is_clamped_to_one(self):
        diagnostic = SimpleNamespace(
            density=0.0,
            risk_state="NORMAL",
            elevated=False,
            high=False,
            explanation="Normal regime.",
        )

        service = FakeDiagnosticService(
            result=diagnostic,
        )

        _current_sparse_consensus_risk(
            FakeDb(10),
            diagnostic_service=service,
            window_size=0,
        )

        self.assertEqual(
            service.calls[0]["window_size"],
            1,
        )

        self.assertEqual(
            service.calls[0]["offset"],
            9,
        )


if __name__ == "__main__":
    unittest.main()
