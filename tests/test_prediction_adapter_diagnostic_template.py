
import unittest
from pathlib import Path


class PredictionAdapterDiagnosticTemplateTests(
    unittest.TestCase
):
    def test_template_contains_status_content(
        self,
    ):
        text = Path(
            "app/templates/prediction_adapter_diagnostic.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Prediction Adapter Diagnostic",
            text,
        )
        self.assertIn(
            "Candidate callables",
            text,
        )


if __name__ == "__main__":
    unittest.main()
