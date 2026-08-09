
import unittest
from pathlib import Path


class CurrentMatchEnrichmentDiscoveryTemplateTests(unittest.TestCase):
    def test_template_contains_discovery_fields(self):
        text = Path(
            "app/templates/current_match_enrichment_discovery.html"
        ).read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Current Match Enrichment Discovery",
            text,
        )
        self.assertIn(
            "Missing performances",
            text,
        )
        self.assertIn(
            "Candidate IDs",
            text,
        )


if __name__ == "__main__":
    unittest.main()
