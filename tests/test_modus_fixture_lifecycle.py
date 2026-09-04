import unittest
from pathlib import Path

from app.schemas.canonical import MatchStatus
from app.services.modus_fixture_lifecycle_service import (
    ModusFixtureLifecycleService,
)


UPCOMING = Path(
    "tests/fixtures/modus_fixture_lifecycle/upcoming.html"
)
COMPLETED = Path(
    "tests/fixtures/modus_fixture_lifecycle/completed.html"
)


class ModusFixtureLifecycleServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ModusFixtureLifecycleService()

    def test_parses_upcoming_fixture_without_fake_score(self):
        card = self.service.parse_cards(
            UPCOMING.read_text(encoding="utf-8")
        )[0]

        self.assertEqual(card.match_id, 20001)
        self.assertEqual(card.status, MatchStatus.SCHEDULED)
        self.assertIsNone(card.player_a_legs)
        self.assertIsNone(card.player_b_legs)

    def test_parses_live_upcoming_card_using_source_game_number(self):
        html = """
        <select id="seriesSelect">
          <option value="26" selected>Series 15</option>
        </select>

        <select id="weekSelect">
          <option value="195" selected>Week 5</option>
        </select>

        <button class="active">Group B</button>

        <article
            class="fixture-card cache-fixture-card fixture-card-upcoming"
            data-source-game-number="74298014"
            data-cache-group="Group B"
        >
          <div class="match-label">22:10</div>
          <div class="player-row">
            <span class="score">0</span>
            <span>Ziggy Schenk</span>
          </div>
          <div class="player-row">
            <span class="score">0</span>
            <span>Richard McKee</span>
          </div>
        </article>
        """

        cards = self.service.parse_cards(html)

        self.assertEqual(len(cards), 1)

        card = cards[0]

        self.assertEqual(
            card.match_id,
            74298014,
        )
        self.assertEqual(
            card.status,
            MatchStatus.SCHEDULED,
        )
        self.assertEqual(
            card.player_a_name,
            "Ziggy Schenk",
        )
        self.assertEqual(
            card.player_b_name,
            "Richard McKee",
        )
        self.assertIsNone(
            card.player_a_legs
        )
        self.assertIsNone(
            card.player_b_legs
        )
        self.assertEqual(
            card.series_id,
            26,
        )
        self.assertEqual(
            card.week_id,
            195,
        )
        self.assertEqual(
            card.group,
            "Group B",
        )

    def test_parses_completed_fixture_with_score(self):
        card = self.service.parse_cards(
            COMPLETED.read_text(encoding="utf-8")
        )[0]

        self.assertEqual(card.status, MatchStatus.COMPLETED)
        self.assertEqual(card.player_a_legs, 4)
        self.assertEqual(card.player_b_legs, 2)

    def test_builds_scheduled_canonical_fixture(self):
        preview = self.service.build_canonical_fixtures(
            UPCOMING.read_text(encoding="utf-8")
        )
        fixture = preview.fixtures[0]

        self.assertEqual(fixture.external_id, "modus-match-20001")
        self.assertEqual(fixture.status, MatchStatus.SCHEDULED)
        self.assertEqual(
            fixture.player_a_external_id,
            "modus-player-player-one",
        )
        self.assertIsNone(fixture.actual_start_at)

    def test_preview_counts_statuses(self):
        upcoming = self.service.build_canonical_fixtures(
            UPCOMING.read_text(encoding="utf-8")
        )
        completed = self.service.build_canonical_fixtures(
            COMPLETED.read_text(encoding="utf-8")
        )

        self.assertEqual(upcoming.scheduled_count, 1)
        self.assertEqual(upcoming.completed_count, 0)
        self.assertEqual(completed.scheduled_count, 0)
        self.assertEqual(completed.completed_count, 1)

    def test_scheduled_to_completed_is_update(self):
        action = self.service.lifecycle_action(
            existing_status=MatchStatus.SCHEDULED,
            incoming_status=MatchStatus.COMPLETED,
        )
        self.assertEqual(action, "update")

    def test_same_status_is_skip(self):
        action = self.service.lifecycle_action(
            existing_status=MatchStatus.SCHEDULED,
            incoming_status=MatchStatus.SCHEDULED,
        )
        self.assertEqual(action, "skip")

    def test_completed_to_scheduled_is_rejected(self):
        action = self.service.lifecycle_action(
            existing_status=MatchStatus.COMPLETED,
            incoming_status=MatchStatus.SCHEDULED,
        )
        self.assertEqual(action, "reject")

    def test_new_fixture_is_insert(self):
        action = self.service.lifecycle_action(
            existing_status=None,
            incoming_status=MatchStatus.SCHEDULED,
        )
        self.assertEqual(action, "insert")


if __name__ == "__main__":
    unittest.main()
