import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.services.upcoming_fixture_intelligence_service import (
    build_upcoming_fixture_intelligence,
)


class UpcomingFixtureIntelligenceTests(
    unittest.TestCase
):
    def setUp(self):
        engine = create_engine(
            "sqlite:///:memory:"
        )

        Base.metadata.create_all(
            bind=engine
        )

        Session = sessionmaker(
            bind=engine
        )

        self.db = Session()

    def tearDown(self):
        self.db.close()

    def add_completed(
        self,
        row_id,
        player_a,
        player_b,
        day,
    ):
        self.db.add(
            Match(
                id=row_id,
                date=date(
                    2026,
                    7,
                    day,
                ),
                tournament="MODUS",
                player_a=player_a,
                player_b=player_b,
                status="completed",
            )
        )

    def test_builds_history_depth_for_scheduled_fixture(
        self,
    ):
        for index in range(
            1,
            6,
        ):
            self.add_completed(
                index,
                "Alpha",
                f"A{index}",
                index,
            )

        for index in range(
            6,
            11,
        ):
            self.add_completed(
                index,
                f"B{index}",
                "Bravo",
                index,
            )

        self.db.add(
            Match(
                id=100,
                date=date(
                    2026,
                    8,
                    10,
                ),
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                status="scheduled",
            )
        )

        self.db.commit()

        fixtures = (
            build_upcoming_fixture_intelligence(
                self.db,
                minimum_history_matches=5,
                today=date(
                    2026,
                    8,
                    1,
                ),
            )
        )

        self.assertEqual(
            len(fixtures),
            1,
        )

        fixture = fixtures[0]

        self.assertEqual(
            fixture.player_a_history_matches,
            5,
        )

        self.assertEqual(
            fixture.player_b_history_matches,
            5,
        )

        self.assertTrue(
            fixture.history_ready
        )

        self.assertEqual(
            fixture.readiness_label,
            "READY",
        )

    def test_non_modus_fixture_excluded(
        self,
    ):
        self.db.add(
            Match(
                id=200,
                date=date(
                    2026,
                    8,
                    10,
                ),
                tournament="PDC",
                player_a="Alpha",
                player_b="Bravo",
                status="scheduled",
            )
        )

        self.db.commit()

        fixtures = (
            build_upcoming_fixture_intelligence(
                self.db
            )
        )

        self.assertEqual(
            fixtures,
            (),
        )


if __name__ == "__main__":
    unittest.main()
