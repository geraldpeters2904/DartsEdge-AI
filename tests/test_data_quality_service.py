import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models.player import Player
from app.models.match import Match
from app.models.match_player_stats import MatchPlayerStats
from app.services.data_quality_service import get_data_quality


class DataQualityServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add_match(self, status, player_a, player_b, stats_count=0):
        match = Match(
            date=date(2026, 10, 1),
            status=status,
            player_a=player_a,
            player_b=player_b,
        )
        self.db.add(match)
        self.db.flush()

        for index in range(stats_count):
            self.db.add(
                MatchPlayerStats(
                    match_id=match.id,
                    player_name=f"Stats Player {index}",
                )
            )

        return match

    def test_missing_players_counts_matches_not_missing_names(self):
        self.db.add(Player(name="Alice"))
        self.db.flush()

        self.add_match("scheduled", "Alice", "Bob")
        self.add_match("scheduled", "Charlie", "Diana")
        self.add_match("scheduled", "Alice", "Alice")

        result = get_data_quality(self.db)

        self.assertEqual(result["scheduled"], 3)
        self.assertEqual(result["missing_players"], 2)

    def test_completed_matches_require_two_statistics_records(self):
        self.add_match("completed", "A", "B", stats_count=0)
        self.add_match("completed", "C", "D", stats_count=1)
        self.add_match("completed", "E", "F", stats_count=2)
        self.add_match("completed", "G", "H", stats_count=3)

        result = get_data_quality(self.db)

        self.assertEqual(result["completed"], 4)
        self.assertEqual(result["match_stats"], 6)
        self.assertEqual(result["missing_match_stats"], 2)

    def test_duplicate_fixture_groups_and_health_score(self):
        self.db.add_all([
            Player(name="Alice"),
            Player(name="Bob"),
        ])
        self.db.flush()

        self.add_match("scheduled", "Alice", "Bob")
        self.add_match("scheduled", "Alice", "Bob")
        self.add_match("completed", "Alice", "Bob", stats_count=2)

        result = get_data_quality(self.db)

        self.assertEqual(result["duplicate_fixtures"], 1)
        self.assertEqual(result["duplicate_players"], 0)
        self.assertEqual(result["missing_players"], 0)
        self.assertEqual(result["missing_match_stats"], 0)
        self.assertEqual(result["health_score"], 95)

    def test_health_score_cannot_be_negative(self):
        for index in range(12):
            self.add_match(
                "completed",
                f"Player A {index}",
                f"Player B {index}",
            )

        result = get_data_quality(self.db)

        self.assertEqual(result["missing_match_stats"], 12)
        self.assertEqual(result["health_score"], 76)


if __name__ == "__main__":
    unittest.main()
