
import unittest

from app.services.current_match_enrichment_discovery_service import (
    _external_match_id,
    _fixture_key,
)


class CurrentMatchEnrichmentDiscoveryTests(unittest.TestCase):
    def test_external_match_id_extracts_numeric_id(self):
        self.assertEqual(
            _external_match_id(
                "modus-match:1901"
            ),
            1901,
        )

    def test_fixture_key_ignores_player_order(self):
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
