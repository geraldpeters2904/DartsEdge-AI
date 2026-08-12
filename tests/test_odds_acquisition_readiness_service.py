import unittest
from datetime import date, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.models.odds_snapshot import OddsSnapshot
from app.services import (
    odds_acquisition_readiness_service as service,
)


class OddsAcquisitionReadinessTests(
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

        self.original_health = (
            service.check_paddy_power_live_health
        )

    def tearDown(self):
        service.check_paddy_power_live_health = (
            self.original_health
        )
        self.db.close()

    @staticmethod
    def ready_health():
        return SimpleNamespace(
            ready=True,
            error=None,
        )

    def test_waiting_when_no_future_fixtures(self):
        service.check_paddy_power_live_health = (
            self.ready_health
        )

        result = (
            service.build_odds_acquisition_readiness(
                self.db
            )
        )

        self.assertEqual(
            result.state,
            "WAITING_FOR_FIXTURES",
        )

        self.assertTrue(
            result.waiting
        )

        self.assertFalse(
            result.ready
        )

    def test_waiting_when_fixture_has_no_odds(self):
        service.check_paddy_power_live_health = (
            self.ready_health
        )

        fixture = Match(
            date=(
                date.today()
                + timedelta(days=1)
            ),
            tournament="MODUS Super Series",
            status="scheduled",
            player_a="Player A",
            player_b="Player B",
        )

        self.db.add(fixture)
        self.db.commit()

        result = (
            service.build_odds_acquisition_readiness(
                self.db
            )
        )

        self.assertEqual(
            result.state,
            "WAITING_FOR_ODDS",
        )

        self.assertEqual(
            result.future_scheduled,
            1,
        )

        self.assertEqual(
            result.current_prices,
            0,
        )

    def test_ready_when_fixture_has_match_winner_odds(
        self,
    ):
        service.check_paddy_power_live_health = (
            self.ready_health
        )

        fixture = Match(
            date=(
                date.today()
                + timedelta(days=1)
            ),
            tournament="MODUS Super Series",
            status="scheduled",
            player_a="Player A",
            player_b="Player B",
        )

        self.db.add(fixture)
        self.db.commit()
        self.db.refresh(fixture)

        self.db.add(
            OddsSnapshot(
                fixture_id=fixture.id,
                bookmaker_code="paddypower",
                market="match_winner",
                selection="Player A",
                decimal_odds=1.80,
            )
        )

        self.db.commit()

        result = (
            service.build_odds_acquisition_readiness(
                self.db
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
            result.priced_fixtures,
            1,
        )

        self.assertEqual(
            result.current_prices,
            1,
        )

    def test_error_when_bookmaker_bridge_not_ready(
        self,
    ):
        service.check_paddy_power_live_health = (
            lambda: SimpleNamespace(
                ready=False,
                error="capture unavailable",
            )
        )

        result = (
            service.build_odds_acquisition_readiness(
                self.db
            )
        )

        self.assertEqual(
            result.state,
            "ERROR",
        )

        self.assertTrue(
            result.error
        )

        self.assertFalse(
            result.bookmaker_ready
        )

        self.assertEqual(
            result.bookmaker_error,
            "capture unavailable",
        )


if __name__ == "__main__":
    unittest.main()
