
import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.services.live_fixture_edge_capture_service import (
    _future_or_current_modus_fixture_count,
)


class LiveFixtureEdgeCaptureTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        self.db = Session()

    def tearDown(self):
        self.db.close()

    def test_counts_current_and_future_scheduled_modus(self):
        self.db.add(
            Match(
                id=1,
                date=date(2026, 8, 9),
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
        self.db.add(
            Match(
                id=3,
                date=date(2026, 8, 8),
                tournament="MODUS",
                player_a="Echo",
                player_b="Foxtrot",
                status="scheduled",
            )
        )
        self.db.commit()

        self.assertEqual(
            _future_or_current_modus_fixture_count(
                self.db,
                today=date(2026, 8, 9),
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()


class LiveFixtureEdgeStoredOddsTests(unittest.TestCase):

    def test_live_edge_uses_stored_odds_without_paddy_capture(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch

        from app.services.live_fixture_edge_capture_service import (
            run_live_fixture_edge_capture,
        )

        db = MagicMock()

        with patch(
            "app.services.live_fixture_edge_capture_service."
            "_future_or_current_modus_fixture_count",
            return_value=2,
        ), patch(
            "app.services.live_fixture_edge_capture_service."
            "build_fixture_edge_rows",
            return_value=(
                SimpleNamespace(
                    bookmaker_odds=2.0,
                    classification="VALUE",
                ),
                SimpleNamespace(
                    bookmaker_odds=None,
                    classification="NO BET",
                ),
            ),
        ):
            report = run_live_fixture_edge_capture(
                db
            )

        self.assertEqual(
            report.future_fixtures,
            2,
        )
        self.assertFalse(
            report.capture_attempted
        )
        self.assertEqual(
            report.edge_rows,
            2,
        )
        self.assertEqual(
            report.priced_edge_rows,
            1,
        )
        self.assertEqual(
            report.value_rows,
            1,
        )
        self.assertIsNone(
            report.error
        )
