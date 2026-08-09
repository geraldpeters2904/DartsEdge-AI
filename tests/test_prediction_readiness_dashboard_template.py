
import unittest
from pathlib import Path


class PredictionReadinessDashboardTemplateTests(unittest.TestCase):
    def test_template_contains_pipeline_sections(self):
        text = Path(
            "app/templates/prediction_readiness_dashboard.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Prediction Readiness Dashboard",
            text,
        )
        self.assertIn(
            "Automation health",
            text,
        )
        self.assertIn(
            "Fixture readiness",
            text,
        )
        self.assertIn(
            "Value fixtures",
            text,
        )


if __name__ == "__main__":
    unittest.main()
