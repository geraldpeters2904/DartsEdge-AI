import unittest
from pathlib import Path
from unittest.mock import patch

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


class ModusFixtureLifecycleHotfixTests(unittest.TestCase):
    def setUp(self):
        self.service = ModusFixtureLifecycleService()

    def test_upcoming_fixture_has_required_canonical_datetime(self):
        preview = self.service.build_canonical_fixtures(
            UPCOMING.read_text(encoding="utf-8")
        )
        fixture = preview.fixtures[0]

        self.assertEqual(fixture.status, MatchStatus.SCHEDULED)
        self.assertIsNotNone(fixture.scheduled_at)
        self.assertIsNone(fixture.actual_start_at)

    def test_completed_fixture_uses_fixture_time_as_actual_start(self):
        preview = self.service.build_canonical_fixtures(
            COMPLETED.read_text(encoding="utf-8")
        )
        fixture = preview.fixtures[0]

        self.assertEqual(fixture.status, MatchStatus.COMPLETED)
        self.assertIsNotNone(fixture.scheduled_at)
        self.assertEqual(fixture.actual_start_at, fixture.scheduled_at)

    def test_upcoming_fixture_still_has_no_fake_scores(self):
        card = self.service.parse_cards(
            UPCOMING.read_text(encoding="utf-8")
        )[0]

        self.assertIsNone(card.player_a_legs)
        self.assertIsNone(card.player_b_legs)


if __name__ == "__main__":
    unittest.main()
