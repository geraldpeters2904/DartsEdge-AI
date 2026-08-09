import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.services.upcoming_fixture_intelligence_service import (
    build_upcoming_fixture_intelligence,
)


class UpcomingFixtureDateFilterTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        self.db = Session()

    def tearDown(self):
        self.db.close()

    def test_past_scheduled_fixture_is_excluded(self):
        self.db.add(
            Match(
                id=1,
                date=date(2026, 7, 15),
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                status="scheduled",
            )
        )
        self.db.add(
            Match(
                id=2,
                date=date(2026, 8, 10),
                tournament="MODUS",
                player_a="Charlie",
                player_b="Delta",
                status="scheduled",
            )
        )
        self.db.commit()

        rows = build_upcoming_fixture_intelligence(
            self.db,
            today=date(2026, 8, 9),
        )

        self.assertEqual(
            [row.fixture_id for row in rows],
            [2],
        )


if __name__ == "__main__":
    unittest.main()
