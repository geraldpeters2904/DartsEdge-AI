import unittest

from app.services.current_match_enrichment_discovery_service import (
    _external_match_id,
    _fixture_key,
)


class CurrentMatchEnrichmentBackwardCompatibilityTests(unittest.TestCase):
    def test_external_match_id_extracts_digits(self):
        self.assertEqual(
            _external_match_id("modus:fixture:18657"),
            18657,
        )

    def test_fixture_key_is_order_independent(self):
        self.assertEqual(
            _fixture_key(
                "James Buckby",
                "Darren Beveridge",
            ),
            _fixture_key(
                "Darren Beveridge",
                "James Buckby",
            ),
        )


if __name__ == "__main__":
    unittest.main()
