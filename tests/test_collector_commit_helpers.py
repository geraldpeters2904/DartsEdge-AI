import unittest

from app.collector.commit_helpers import (
    find_match_by_external_id,
    map_player_external_id,
    optional_participant_name,
    participant_name,
    player_name_for_external_id,
)
from app.models.canonical_data import ProviderEntityMapping
from app.models.match import Match
from app.models.player import Player
from app.schemas.canonical import CanonicalMatchResult, SourceReference
from tests.helpers.database import create_test_session


class CollectorCommitHelperTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

    def tearDown(self):
        self.db.close()

    def build_result(self):
        return CanonicalMatchResult(
            match_external_id="match-1",
            player_a_external_id="player-a",
            player_b_external_id="player-b",
            winner_external_id="player-a",
            player_a_legs=4,
            player_b_legs=2,
            source=SourceReference(
                provider="manual-research",
                external_id="match-1",
                retrieved_at="2026-07-28T10:30:00",
                competition_code="MODUS",
            ),
        )

    def test_match_is_found_through_fixture_mapping(self):
        match = Match(
            player_a="Player A",
            player_b="Player B",
        )
        self.db.add(match)
        self.db.flush()

        self.db.add(
            ProviderEntityMapping(
                provider="manual-research",
                entity_type="fixture",
                external_id="match-1",
                internal_id=match.id,
            )
        )
        self.db.commit()

        found = find_match_by_external_id(
            db=self.db,
            provider="manual-research",
            match_external_id="match-1",
        )

        self.assertEqual(found.id, match.id)

    def test_missing_fixture_mapping_returns_none(self):
        found = find_match_by_external_id(
            db=self.db,
            provider="manual-research",
            match_external_id="missing",
        )

        self.assertIsNone(found)

    def test_player_name_is_resolved_from_external_id(self):
        player = Player(name="Player A")
        self.db.add(player)
        self.db.flush()

        self.db.add(
            ProviderEntityMapping(
                provider="manual-research",
                entity_type="player",
                external_id="player-a",
                internal_id=player.id,
            )
        )
        self.db.commit()

        name = player_name_for_external_id(
            db=self.db,
            provider="manual-research",
            external_id="player-a",
            fallback="Fallback",
        )

        self.assertEqual(name, "Player A")

    def test_participant_name_resolves_both_players(self):
        result = self.build_result()

        self.assertEqual(
            participant_name(
                external_id="player-a",
                result=result,
                player_a_name="Player A",
                player_b_name="Player B",
            ),
            "Player A",
        )

        self.assertEqual(
            participant_name(
                external_id="player-b",
                result=result,
                player_a_name="Player A",
                player_b_name="Player B",
            ),
            "Player B",
        )

    def test_optional_participant_allows_none(self):
        self.assertIsNone(
            optional_participant_name(
                external_id=None,
                result=self.build_result(),
                player_a_name="Player A",
                player_b_name="Player B",
            )
        )

    def test_mapping_external_player_id(self):
        player = Player(name="Player A")
        self.db.add(player)
        self.db.commit()

        map_player_external_id(
            db=self.db,
            provider="manual-research",
            external_id="player-a",
            player_name="Player A",
            competition_code="MODUS",
        )

        mapping = (
            self.db.query(ProviderEntityMapping)
            .filter_by(
                provider="manual-research",
                entity_type="player",
                external_id="player-a",
            )
            .one()
        )

        self.assertEqual(mapping.internal_id, player.id)
        self.assertEqual(mapping.competition_code, "MODUS")


if __name__ == "__main__":
    unittest.main()