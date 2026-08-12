import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.services.stale_scheduled_fixture_diagnostic_service import (
    build_stale_scheduled_fixture_diagnostic,
)


class StaleScheduledFixtureDiagnosticTests(
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

    def test_no_stale_rows_is_healthy(self):
        result = (
            build_stale_scheduled_fixture_diagnostic(
                self.db,
                today=date(
                    2026,
                    8,
                    12,
                ),
            )
        )

        self.assertTrue(
            result.healthy
        )

        self.assertEqual(
            result.stale_count,
            0,
        )

    def test_past_scheduled_rows_are_flagged(self):
        self.db.add(
            Match(
                id=1,
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

        result = (
            build_stale_scheduled_fixture_diagnostic(
                self.db,
                today=date(
                    2026,
                    8,
                    12,
                ),
            )
        )

        self.assertFalse(
            result.healthy
        )

        self.assertEqual(
            result.stale_count,
            1,
        )

        self.assertEqual(
            result.oldest_date,
            date(
                2026,
                8,
                10,
            ),
        )

    def test_future_scheduled_rows_are_not_stale(self):
        self.db.add(
            Match(
                id=2,
                date=date(
                    2026,
                    8,
                    14,
                ),
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                status="scheduled",
            )
        )

        self.db.commit()

        result = (
            build_stale_scheduled_fixture_diagnostic(
                self.db,
                today=date(
                    2026,
                    8,
                    12,
                ),
            )
        )

        self.assertTrue(
            result.healthy
        )

        self.assertEqual(
            result.stale_count,
            0,
        )


if __name__ == "__main__":
    unittest.main()
