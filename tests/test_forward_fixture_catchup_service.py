import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.services.forward_fixture_catchup_service import (
    stale_scheduled_modus_fixtures,
)


class ForwardFixtureCatchupTests(
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

    def test_stale_modus_fixture_is_candidate(
        self,
    ):
        self.db.add(
            Match(
                id=1,
                date=date(
                    2026,
                    7,
                    15,
                ),
                tournament="MODUS",
                player_a="Lewis Pride",
                player_b="Devon Petersen",
                status="scheduled",
            )
        )

        self.db.commit()

        rows = (
            stale_scheduled_modus_fixtures(
                self.db,
                today=date(
                    2026,
                    8,
                    9,
                ),
            )
        )

        self.assertEqual(
            len(rows),
            1,
        )

        self.assertEqual(
            rows[0].fixture_id,
            1,
        )

    def test_future_fixture_not_candidate(
        self,
    ):
        self.db.add(
            Match(
                id=2,
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

        rows = (
            stale_scheduled_modus_fixtures(
                self.db,
                today=date(
                    2026,
                    8,
                    9,
                ),
            )
        )

        self.assertEqual(
            rows,
            (),
        )

    def test_non_modus_fixture_not_candidate(
        self,
    ):
        self.db.add(
            Match(
                id=3,
                date=date(
                    2026,
                    7,
                    1,
                ),
                tournament="PDC",
                player_a="Alpha",
                player_b="Bravo",
                status="scheduled",
            )
        )

        self.db.commit()

        rows = (
            stale_scheduled_modus_fixtures(
                self.db,
                today=date(
                    2026,
                    8,
                    9,
                ),
            )
        )

        self.assertEqual(
            rows,
            (),
        )


if __name__ == "__main__":
    unittest.main()
