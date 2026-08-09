import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.models.odds_movement import OddsMovement
from app.models.odds_snapshot import OddsSnapshot
from app.services.live_operations_centre_service import (
    build_live_ops_summary,
    recent_odds_movements,
)


class LiveOperationsCentreServiceTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        self.db = Session()

    def tearDown(self):
        self.db.close()

    def test_summary_counts_matches_and_odds(self):
        self.db.add(
            Match(
                date=datetime(2026, 8, 9).date(),
                tournament="MODUS",
                player_a="Alpha",
                player_b="Bravo",
                status="scheduled",
            )
        )

        self.db.add(
            Match(
                date=datetime(2026, 8, 8).date(),
                tournament="MODUS",
                player_a="Charlie",
                player_b="Delta",
                status="completed",
            )
        )

        self.db.add(
            OddsSnapshot(
                fixture_id=1,
                bookmaker_code="paddypower",
                market="match_winner",
                selection="Alpha",
                decimal_odds=2.0,
                implied_probability=50.0,
                captured_at=datetime(2026, 8, 9, 10, 0),
            )
        )

        self.db.commit()

        summary = build_live_ops_summary(self.db)

        self.assertEqual(summary.scheduled_matches, 1)
        self.assertEqual(summary.completed_matches, 1)
        self.assertEqual(summary.odds_snapshots, 1)

    def test_recent_movements_newest_first(self):
        self.db.add_all(
            [
                OddsMovement(
                    fixture_id=10,
                    bookmaker_code="paddypower",
                    market="match_winner",
                    selection="Alpha",
                    previous_odds=2.10,
                    new_odds=2.00,
                    absolute_change=-0.10,
                    percentage_change=-4.7619,
                    direction="shortening",
                    detected_at=datetime(2026, 8, 9, 10, 0),
                ),
                OddsMovement(
                    fixture_id=11,
                    bookmaker_code="paddypower",
                    market="match_winner",
                    selection="Bravo",
                    previous_odds=1.80,
                    new_odds=1.85,
                    absolute_change=0.05,
                    percentage_change=2.7778,
                    direction="drifting",
                    detected_at=datetime(2026, 8, 9, 10, 5),
                ),
            ]
        )

        self.db.commit()

        rows = recent_odds_movements(self.db, limit=10)

        self.assertEqual(rows[0].fixture_id, 11)
        self.assertEqual(rows[1].fixture_id, 10)


if __name__ == "__main__":
    unittest.main()
