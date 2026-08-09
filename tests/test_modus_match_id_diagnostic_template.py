import unittest
from pathlib import Path


class ModusMatchIdDiagnosticTemplateTests(unittest.TestCase):
    def test_template_contains_diagnostic_fields(self):
        text = Path(
            "app/templates/modus_match_id_diagnostic.html"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "MODUS Match-ID Extraction Diagnostic",
            text,
        )
        self.assertIn("Raw match links", text)
        self.assertIn("Canonical IDs retained", text)


if __name__ == "__main__":
    unittest.main()
