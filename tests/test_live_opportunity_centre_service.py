import unittest
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime, timedelta

from app.services.live_opportunity_centre_service import (
    _state,
    build_live_opportunity_centre,
)


class LiveOpportunityLifecycleTests(unittest.TestCase):
    @patch(
        "app.services.live_opportunity_centre_service.build_prediction_centre"
    )
    @patch(
        "app.services.live_opportunity_centre_service._history",
        return_value=[],
    )
    def test_uses_effective_stake_not_shadow_strategy_stake(
        self,
        history,
        centre,
    ):
        centre.return_value = {
            "centre_date": "2026-10-03",
            "portfolio": {},
            "active_strategy": None,
            "cards": [
                {
                    "fixture": SimpleNamespace(
                        id=1,
                        date="2026-10-03",
                        tournament="MODUS",
                        player_a="Player A",
                        player_b="Player B",
                    ),
                    "opportunity": {
                        "selection": "Player A",
                        "probability": 62.0,
                        "model_confidence": 78.0,
                    },
                    "assessment": SimpleNamespace(
                        expected_value_percent=10.0,
                        edge_percent=6.0,
                        recommended_stake=18.0,
                    ),
                    "price": SimpleNamespace(
                        bookmaker="Paddy Power",
                        decimal_odds=2.0,
                    ),
                    "decision_intelligence": {
                        "score": 72,
                        "grade": "Strong",
                        "recommendation": "SMALL BET",
                        "strategy_suggested_stake": 0.0,
                        "effective_stake": 12.0,
                        "consensus_score": None,
                        "steam_direction": None,
                        "steam_strength": None,
                        "coordinated_move": False,
                    },
                },
            ],
        }

        result = build_live_opportunity_centre(
            object(),
            persist=False,
        )

        self.assertEqual(
            result["opportunities"][0].suggested_stake,
            12.0,
        )
        self.assertEqual(
            result["opportunities"][0].kelly_stake,
            18.0,
        )

    def test_new_state(self):
        self.assertEqual(
            _state(
                current_score=75,
                first_score=75,
                peak_score=75,
                age_minutes=5,
            ),
            "NEW",
        )

    def test_peak_state(self):
        self.assertEqual(
            _state(
                current_score=92,
                first_score=80,
                peak_score=92,
                age_minutes=30,
            ),
            "PEAK",
        )

    def test_mature_state(self):
        self.assertEqual(
            _state(
                current_score=84,
                first_score=80,
                peak_score=86,
                age_minutes=35,
            ),
            "MATURE",
        )

    def test_declining_state(self):
        self.assertEqual(
            _state(
                current_score=74,
                first_score=80,
                peak_score=85,
                age_minutes=40,
            ),
            "DECLINING",
        )


if __name__ == "__main__":
    unittest.main()
