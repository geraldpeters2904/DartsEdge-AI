
import unittest

from app.services.current_match_enrichment_discovery_service import (
    _resolve_by_occurrence,
)


class FakeMatch:
    def __init__(self, match_id):
        self.id = match_id


class CurrentMatchIdResolverTests(unittest.TestCase):
    def test_equal_occurrence_counts_resolve_in_order(self):
        internal = [
            FakeMatch(10),
            FakeMatch(20),
        ]

        official = [
            (1001, object()),
            (1002, object()),
        ]

        result = _resolve_by_occurrence(
            internal,
            official,
        )

        self.assertEqual(
            result[10][0],
            1001,
        )
        self.assertEqual(
            result[20][0],
            1002,
        )
        self.assertEqual(
            result[10][2],
            "resolved",
        )

    def test_mismatched_occurrence_counts_are_ambiguous(self):
        internal = [
            FakeMatch(10),
            FakeMatch(20),
        ]

        official = [
            (1001, object()),
        ]

        result = _resolve_by_occurrence(
            internal,
            official,
        )

        self.assertEqual(
            result[10][2],
            "ambiguous",
        )
        self.assertEqual(
            result[20][2],
            "ambiguous",
        )


if __name__ == "__main__":
    unittest.main()
