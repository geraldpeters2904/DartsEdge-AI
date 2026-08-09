
import unittest
from pathlib import Path


class PredictionAdapterSelfTestTemplateTests(unittest.TestCase):
    def test_template_contains_self_test_fields(self):
        text = Path(
            "app/templates/prediction_adapter_self_test.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Prediction Adapter Self-Test",
            text,
        )
        self.assertIn(
            "Minimum history",
            text,
        )
        self.assertIn(
            "fair odds",
            text,
        )


if __name__ == "__main__":
    unittest.main()
