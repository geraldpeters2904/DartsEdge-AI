import unittest
from types import SimpleNamespace

from app.services.player_name_service import (
    canonical_player_display_name,
    normalise_player_name,
    resolve_player_by_name,
)


class FakeQuery:
    def __init__(self, players):
        self.players = players

    def filter(self, expression):
        return self

    def first(self):
        return None

    def all(self):
        return self.players


class FakeDb:
    def __init__(self, players):
        self.players = players

    def query(self, model):
        return FakeQuery(self.players)


class PlayerNameResolutionTests(unittest.TestCase):
    def test_canonicalises_display_name_without_lowercasing(self):
        self.assertEqual(
            canonical_player_display_name(
                "  Noa-Lynn van_Leuven_ "
            ),
            "Noa-Lynn van Leuven",
        )

    def test_normalises_underscore_case_and_whitespace(self):
        self.assertEqual(
            normalise_player_name("  Keanu   Van_Velzen "),
            "keanu van velzen",
        )

    def test_resolves_existing_player_name_variant(self):
        existing = SimpleNamespace(id=94, name="Keanu van Velzen")
        db = FakeDb([existing])

        player = resolve_player_by_name(db, "Keanu Van_Velzen")

        self.assertIs(player, existing)

    def test_different_player_is_not_matched(self):
        db = FakeDb([SimpleNamespace(id=95, name="Keanu van Dijk")])

        player = resolve_player_by_name(db, "Keanu Van_Velzen")

        self.assertIsNone(player)


if __name__ == "__main__":
    unittest.main()
