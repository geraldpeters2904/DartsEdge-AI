import unittest
from datetime import datetime
from types import SimpleNamespace

from app.services.opportunity_replay_service import build_events


def point(
    row_id,
    *,
    minute,
    score,
    recommendation="WATCH",
    lifecycle_state="BUILDING",
    odds=2.0,
    consensus=70.0,
    coordinated=False,
    steam_direction=None,
    steam_strength=None,
):
    return SimpleNamespace(
        id=row_id,
        captured_at=datetime(2026, 8, 7, 10, minute),
        decision_score=score,
        recommendation=recommendation,
        lifecycle_state=lifecycle_state,
        decimal_odds=odds,
        expected_value_percent=5.0,
        consensus_score=consensus,
        coordinated_move=coordinated,
        steam_direction=steam_direction,
        steam_strength=steam_strength,
    )


class OpportunityReplayServiceTests(unittest.TestCase):
    def test_builds_threshold_and_lifecycle_events(self):
        events = build_events([
            point(1, minute=0, score=76, lifecycle_state="NEW"),
            point(
                2,
                minute=15,
                score=82,
                recommendation="SMALL BET",
                lifecycle_state="BUILDING",
                odds=2.08,
            ),
            point(
                3,
                minute=30,
                score=91,
                recommendation="BET",
                lifecycle_state="PEAK",
                consensus=92.0,
                coordinated=True,
                steam_direction="shortening",
                steam_strength="strong",
            ),
        ])

        messages = [event.message for event in events]

        self.assertIn("Decision Score crossed 80.", messages)
        self.assertIn("Decision Score crossed 90.", messages)
        self.assertTrue(any("Lifecycle changed" in m for m in messages))
        self.assertTrue(any("Recommendation changed" in m for m in messages))
        self.assertTrue(
            any(
                "Coordinated market move detected" in m
                for m in messages
            )
        )


if __name__ == "__main__":
    unittest.main()
