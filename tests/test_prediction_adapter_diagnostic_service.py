
import unittest

from app.services.prediction_adapter_diagnostic_service import (
    diagnose_prediction_adapter,
)


class PredictionAdapterDiagnosticTests(
    unittest.TestCase
):
    def test_diagnostic_returns_candidates(
        self,
    ):
        result = diagnose_prediction_adapter()

        self.assertGreater(
            len(result.candidates),
            0,
        )

    def test_ready_result_has_resolution(
        self,
    ):
        result = diagnose_prediction_adapter()

        if result.ready:
            self.assertIsNotNone(
                result.module_name
            )
            self.assertIsNotNone(
                result.function_name
            )


if __name__ == "__main__":
    unittest.main()
