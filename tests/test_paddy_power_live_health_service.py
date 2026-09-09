import unittest
from unittest.mock import patch

from app.services.paddy_power_live_bridge import (
    PaddyPowerBridgeResolution,
)
from app.services.paddy_power_live_health_service import (
    check_paddy_power_live_health,
)


class PaddyPowerLiveHealthTests(
    unittest.TestCase
):
    @patch(
        "app.services.paddy_power_live_health_service.resolve_capture_callable"
    )
    def test_ready_when_callable_resolves(
        self,
        resolve,
    ):
        resolve.return_value = (
            PaddyPowerBridgeResolution(
                module_name="app.services.fake",
                function_name="capture",
                callable=lambda: [],
            )
        )

        health = (
            check_paddy_power_live_health()
        )

        self.assertTrue(
            health.ready
        )
        self.assertEqual(
            health.function_name,
            "capture",
        )

    @patch(
        "app.services.paddy_power_live_health_service.resolve_capture_callable"
    )
    def test_not_ready_when_resolution_fails(
        self,
        resolve,
    ):
        resolve.side_effect = (
            RuntimeError(
                "not available"
            )
        )

        health = (
            check_paddy_power_live_health()
        )

        self.assertFalse(
            health.ready
        )
        self.assertIn(
            "not available",
            health.error,
        )


if __name__ == "__main__":
    unittest.main()

class PaddyPowerFixtureDiagnosticsTests(unittest.TestCase):

    def test_reports_markets_latest_capture_and_profile_freshness_read_only(
        self,
    ):
        from datetime import date, datetime
        from types import SimpleNamespace

        from app.models.match import Match
        from app.models.odds_snapshot import OddsSnapshot
        from app.models.player import Player
        from app.models.player_career_profile import PlayerCareerProfile
        from app.services.paddy_power_live_health_service import (
            build_paddy_power_fixture_diagnostics,
        )

        fixture = SimpleNamespace(
            id=101,
            date=date(2026, 9, 10),
            player_a="Player A",
            player_b="Player B",
        )

        snapshots = [
            SimpleNamespace(
                market="match_winner",
                captured_at=datetime(2026, 9, 9, 18, 0, 0),
            ),
            SimpleNamespace(
                market="handicap",
                captured_at=datetime(2026, 9, 9, 18, 5, 0),
            ),
            SimpleNamespace(
                market="total_legs",
                captured_at=datetime(2026, 9, 9, 18, 4, 0),
            ),
        ]

        players = {
            "Player A": SimpleNamespace(id=1, name="Player A"),
            "Player B": SimpleNamespace(id=2, name="Player B"),
        }

        profiles = {
            1: SimpleNamespace(
                player_id=1,
                competition_code="ALL",
                latest_match_date=date(2026, 9, 1),
            ),
            2: SimpleNamespace(
                player_id=2,
                competition_code="ALL",
                latest_match_date=date(2026, 2, 1),
            ),
        }

        class Query:
            def __init__(self, rows):
                self.rows = list(rows)

            def filter(self, *args):
                return self

            def order_by(self, *args):
                return self

            def all(self):
                return list(self.rows)

            def one_or_none(self):
                if len(self.rows) > 1:
                    raise AssertionError("Expected at most one row")
                return self.rows[0] if self.rows else None

        class DB:
            def __init__(self):
                self.player_names = ["Player A", "Player B"]
                self.profile_ids = [1, 2]
                self.write_calls = []

            def query(self, model):
                if model is Match:
                    return Query([fixture])
                if model is OddsSnapshot:
                    return Query(snapshots)
                if model is Player:
                    return Query([
                        players[self.player_names.pop(0)]
                    ])
                if model is PlayerCareerProfile:
                    return Query([
                        profiles[self.profile_ids.pop(0)]
                    ])
                raise AssertionError(f"Unexpected query model: {model}")

            def add(self, *args, **kwargs):
                self.write_calls.append(("add", args, kwargs))

            def commit(self):
                self.write_calls.append(("commit", (), {}))

            def flush(self):
                self.write_calls.append(("flush", (), {}))

        db = DB()

        rows = build_paddy_power_fixture_diagnostics(
            db,
            today=date(2026, 9, 9),
        )

        self.assertEqual(len(rows), 1)

        row = rows[0]

        self.assertEqual(row["fixture_id"], 101)
        self.assertEqual(
            row["markets"],
            ["handicap", "match_winner", "total_legs"],
        )
        self.assertEqual(
            row["latest_capture_at"],
            datetime(2026, 9, 9, 18, 5, 0),
        )
        self.assertFalse(row["player_a_stale"])
        self.assertTrue(row["player_b_stale"])
        self.assertFalse(row["leg_markets_eligible"])
        self.assertEqual(db.write_calls, [])
