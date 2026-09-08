import unittest
from datetime import date

from app.models.match import Match
from app.services.fixture_service import get_scheduled_fixtures
from tests.helpers.database import create_test_session


class ScheduledFixtureTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

    def tearDown(self):
        self.db.close()

    def test_excludes_past_scheduled_fixtures(self):
        self.db.add_all(
            [
                Match(
                    id=1,
                    date=date(2026, 9, 4),
                    tournament="MODUS",
                    player_a="Past A",
                    player_b="Past B",
                    status="scheduled",
                ),
                Match(
                    id=2,
                    date=date(2026, 9, 8),
                    tournament="MODUS",
                    player_a="Today A",
                    player_b="Today B",
                    status="scheduled",
                ),
                Match(
                    id=3,
                    date=date(2026, 9, 9),
                    tournament="MODUS",
                    player_a="Future A",
                    player_b="Future B",
                    status="scheduled",
                ),
            ]
        )
        self.db.commit()

        fixtures = get_scheduled_fixtures(
            self.db,
            today=date(2026, 9, 8),
        )

        self.assertEqual(
            [fixture.id for fixture in fixtures],
            [2, 3],
        )


if __name__ == "__main__":
    unittest.main()
