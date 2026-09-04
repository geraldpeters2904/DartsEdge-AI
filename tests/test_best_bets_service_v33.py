import unittest
from unittest.mock import patch
from datetime import date
from types import SimpleNamespace

from app.prediction_config import (
    ACTIVE_PREDICTION_MODEL_NAME,
)

from app.services.best_bets_service import (
    _confidence_label,
    _minimum_odds,
    build_best_bets,
)


class FakeQuery:
    def __init__(self, matches):
        self.matches = matches

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return self.matches


class FakeDb:
    def __init__(self, matches):
        self.matches = matches

    def query(self, model):
        return FakeQuery(
            self.matches
        )


class FakeSnapshotEngine:
    def build_match_snapshot(
        self,
        db,
        match_id,
    ):
        history = SimpleNamespace(
            matches_available=10
        )

        return SimpleNamespace(
            match_id=match_id,
            player_a=SimpleNamespace(
                advanced_features=history
            ),
            player_b=SimpleNamespace(
                advanced_features=history
            ),
        )


class FakeContribution:
    feature_name = "scoring_power"
    raw_edge = 10.0
    normalised_edge = 0.1
    weight = 0.15
    weighted_score = 0.015
    confidence = 100.0
    explanation = (
        "Player A has stronger scoring power."
    )


class FakePrediction:
    player_a_name = "Player A"
    player_b_name = "Player B"
    player_a_probability = 62.4
    player_b_probability = 37.6
    predicted_winner = "Player A"
    confidence = 74.0
    model_score = 0.17
    contributions = (
        FakeContribution(),
    )
    explanation = (
        "Player A has stronger scoring power.",
    )


class FakeModel:
    def predict(self, snapshot):
        return FakePrediction()


class FakeRegistry:
    def get_registered(self, name):
        return SimpleNamespace(
            name=name,
            version=ACTIVE_PREDICTION_MODEL_NAME,
            model=FakeModel(),
        )


class BestBetsServiceV33Tests(
    unittest.TestCase
):
    def test_confidence_contract(self):
        self.assertEqual(
            _confidence_label(70.0),
            ("High", 5),
        )
        self.assertEqual(
            _confidence_label(62.0),
            ("Good", 4),
        )
        self.assertEqual(
            _confidence_label(55.0),
            ("Moderate", 3),
        )
        self.assertEqual(
            _confidence_label(54.9),
            ("Low", 2),
        )

    def test_minimum_odds_uses_five_percent_buffer(self):
        self.assertEqual(
            _minimum_odds(2.00),
            2.10,
        )

    def test_builds_legacy_and_v33_fields(self):
        match = SimpleNamespace(
            id=123,
            date=date(2026, 8, 6),
            tournament="MODUS",
            player_a="Player A",
            player_b="Player B",
            status="scheduled",
        )

        result = build_best_bets(
            FakeDb([match]),
            limit=5,
            snapshot_engine=(
                FakeSnapshotEngine()
            ),
            model_registry=(
                FakeRegistry()
            ),
        )

        self.assertEqual(
            len(result),
            1,
        )

        item = result[0]

        self.assertEqual(
            item["selection"],
            "Player A",
        )
        self.assertEqual(
            item["probability"],
            62.4,
        )
        self.assertEqual(
            item["confidence"],
            "Good",
        )
        self.assertEqual(
            item["stars"],
            4,
        )
        self.assertEqual(
            item["fair_odds"],
            1.6,
        )
        self.assertEqual(
            item["model_name"],
            ACTIVE_PREDICTION_MODEL_NAME,
        )
        self.assertEqual(
            item["model_version"],
            ACTIVE_PREDICTION_MODEL_NAME,
        )
        self.assertEqual(
            item["player_b_probability"],
            37.6,
        )
        self.assertEqual(
            item["contributions"][0][
                "feature"
            ],
            "scoring_power",
        )
        self.assertEqual(
            item["contributions"][0][
                "label"
            ],
            "Scoring Power",
        )
        self.assertEqual(
            item["contributions"][0][
                "direction"
            ],
            "player_a",
        )
        self.assertEqual(
            item["contributions"][0][
                "impact_percent"
            ],
            15.0,
        )


    @patch(
        "app.services.best_bets_service."
        "_latest_paddy_power_match_winner_price"
    )
    def test_attaches_latest_paddy_power_match_winner_odds(
        self,
        latest_price,
    ):
        latest_price.return_value = SimpleNamespace(
            decimal_odds=1.95,
            bookmaker_code="paddypower",
        )

        match = SimpleNamespace(
            id=123,
            date=date(2026, 8, 6),
            tournament="MODUS",
            player_a="Player A",
            player_b="Player B",
            status="scheduled",
        )

        result = build_best_bets(
            FakeDb([match]),
            limit=5,
            snapshot_engine=(
                FakeSnapshotEngine()
            ),
            model_registry=(
                FakeRegistry()
            ),
        )

        self.assertEqual(
            len(result),
            1,
        )
        self.assertEqual(
            result[0]["market_odds"],
            1.95,
        )
        self.assertEqual(
            result[0]["bookmaker"],
            "Paddy Power",
        )

        latest_price.assert_called_once_with(
            unittest.mock.ANY,
            fixture_id=123,
            selection="Player A",
        )


if __name__ == "__main__":
    unittest.main()
