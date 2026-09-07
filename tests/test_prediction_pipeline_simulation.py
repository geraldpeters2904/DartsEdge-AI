import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import prediction_pipeline


class _Query:
    def __init__(self, players):
        self.players = players
        self.name = None

    def filter(self, condition):
        self.name = condition.right.value
        return self

    def first(self):
        return self.players.get(self.name)


class _Db:
    def __init__(self):
        self.players = {
            "Player A": SimpleNamespace(
                name="Player A",
                elo=1500,
                average=90.0,
                checkout=40.0,
            ),
            "Player B": SimpleNamespace(
                name="Player B",
                elo=1500,
                average=85.0,
                checkout=35.0,
            ),
        }

    def query(self, model):
        return _Query(self.players)


class PredictionPipelineSimulationTests(unittest.TestCase):

    def test_passes_leg_probability_to_simulation(self):
        profile_a = {
            "name": "Player A",
            "elo": 1500,
            "dartsedge_rating": 70.0,
            "form": {"expected": 1.0},
        }
        profile_b = {
            "name": "Player B",
            "elo": 1500,
            "dartsedge_rating": 65.0,
            "form": {"expected": 1.0},
        }

        with (
            patch.object(
                prediction_pipeline,
                "get_player_profile",
                side_effect=[profile_a, profile_b],
            ),
            patch.object(
                prediction_pipeline,
                "compare_players",
                return_value={},
            ),
            patch.object(
                prediction_pipeline,
                "win_probability",
                return_value=0.55,
            ),
            patch.object(
                prediction_pipeline,
                "leg_win_probability",
                return_value=0.65,
            ),
            patch.object(
                prediction_pipeline,
                "one80_markets",
                return_value={},
            ),
            patch.object(
                prediction_pipeline,
                "first_180_market",
                return_value={
                    "player_a": 0.5,
                    "player_b": 0.5,
                },
            ),
            patch.object(
                prediction_pipeline,
                "get_head_to_head",
                return_value={},
            ),
            patch.object(
                prediction_pipeline,
                "build_prediction_factors",
                return_value={},
            ),
            patch.object(
                prediction_pipeline,
                "simulate_match",
                return_value={
                    "player_a_win": 0.5,
                    "player_b_win": 0.5,
                },
            ) as simulate,
            patch.object(
                prediction_pipeline,
                "build_confidence_breakdown",
                return_value={},
            ),
            patch.object(
                prediction_pipeline,
                "build_match_explanation",
                return_value={},
            ),
            patch.object(
                prediction_pipeline,
                "build_prediction_explainability",
                return_value={},
            ),
            patch.object(
                prediction_pipeline,
                "build_recommendation",
                return_value={
                    "market": "Match Winner",
                    "selection": "Player A",
                    "probability": 55.0,
                    "fair_odds": 1.82,
                    "confidence": "Moderate",
                },
            ),
            patch.object(
                prediction_pipeline,
                "build_trading_opportunities",
                return_value=[],
            ),
        ):
            prediction_pipeline.build_prediction(
                _Db(),
                "Player A",
                "Player B",
            )

        simulate.assert_called_once_with(
            profile_a,
            profile_b,
            leg_win_prob_a=0.65,
            best_of=7,
        )


if __name__ == "__main__":
    unittest.main()
