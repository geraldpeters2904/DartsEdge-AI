import unittest
from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.services.fixture_acquisition_readiness_service import (
    build_fixture_acquisition_readiness,
)


class FixtureAcquisitionReadinessTests(
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

        self.status = SimpleNamespace(
            latest_series="Series 15",
            latest_week="Week 2",
            last_run_at=(
                "2026-08-12T14:50:24"
            ),
            last_error=None,
        )

    def tearDown(self):
        self.db.close()

    def test_no_published_fixtures_is_waiting(self):
        result = (
            build_fixture_acquisition_readiness(
                self.db,
                monitor_status=self.status,
                today=date(
                    2026,
                    8,
                    12,
                ),
            )
        )

        self.assertEqual(
            result.state,
            "WAITING",
        )

        self.assertTrue(
            result.waiting
        )

        self.assertFalse(
            result.error
        )

    def test_future_fixture_is_ready(self):
        self.db.add(
            Match(
                id=1,
                date=date(
                    2026,
                    8,
                    13,
                ),
                tournament=(
                    "MODUS Super Series"
                ),
                player_a="Alpha",
                player_b="Bravo",
                status="scheduled",
            )
        )

        self.db.commit()

        result = (
            build_fixture_acquisition_readiness(
                self.db,
                monitor_status=self.status,
                today=date(
                    2026,
                    8,
                    12,
                ),
            )
        )

        self.assertEqual(
            result.state,
            "READY",
        )

        self.assertTrue(
            result.ready
        )

        self.assertEqual(
            result.future_scheduled,
            1,
        )

    def test_stale_fixture_is_flagged(self):
        self.db.add(
            Match(
                id=2,
                date=date(
                    2026,
                    8,
                    11,
                ),
                tournament=(
                    "MODUS Super Series"
                ),
                player_a="Alpha",
                player_b="Bravo",
                status="scheduled",
            )
        )

        self.db.commit()

        result = (
            build_fixture_acquisition_readiness(
                self.db,
                monitor_status=self.status,
                today=date(
                    2026,
                    8,
                    12,
                ),
            )
        )

        self.assertEqual(
            result.state,
            "STALE",
        )

        self.assertTrue(
            result.stale
        )

    def test_monitor_error_is_error(self):
        status = SimpleNamespace(
            latest_series="Series 15",
            latest_week="Week 2",
            last_run_at=(
                "2026-08-12T14:50:24"
            ),
            last_error="Browser failed.",
        )

        result = (
            build_fixture_acquisition_readiness(
                self.db,
                monitor_status=status,
                today=date(
                    2026,
                    8,
                    12,
                ),
            )
        )

        self.assertEqual(
            result.state,
            "ERROR",
        )

        self.assertTrue(
            result.error
        )


if __name__ == "__main__":
    unittest.main()
