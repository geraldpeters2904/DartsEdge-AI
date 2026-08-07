import unittest
from types import SimpleNamespace

from app.services.prediction_context_service import (
    build_prediction_context,
    context_summary,
    context_to_opportunity,
)


class FakeSnapshotEngine:
    def build_match_snapshot(
        self,
        db,
        match_id,
        *,
        competition_code=None,
    ):
        history_a = SimpleNamespace(
            matches_available=40
        )
        history_b = SimpleNamespace(
            matches_available=35
        )

        return SimpleNamespace(
            match_id=match_id,
            player_a=SimpleNamespace(
                advanced_features=history_a
            ),
            player_b=SimpleNamespace(
                advanced_features=history_b
            ),
        )


class FakeContribution:
    feature_name = "scoring_power"
    raw_edge = 12.0
    normalised_edge = 0.075
    weight = 0.15
    weighted_score = 0.01125
    confidence = 100.0
    explanation = (
        "Alpha has the stronger scoring power."
    )


class FakePrediction:
    player_a_name = "Alpha"
    player_b_name = "Bravo"
    player_a_probability = 61.2
    player_b_probability = 38.8
    predicted_winner = "Alpha"
    confidence = 78.0
    model_score = 0.151
    explanation = (
        "Alpha has the stronger scoring power.",
    )
    contributions = (
        FakeContribution(),
    )


class FakeModel:
    def predict(self, snapshot):
        return FakePrediction()


class FakeRegistry:
    def get_registered(self, name):
        return SimpleNamespace(
            name=name,
            version="transparent-v3.3",
            model=FakeModel(),
        )


class PredictionContextServiceTests(
    unittest.TestCase
):
    def build(self):
        return build_prediction_context(
            object(),
            123,
            snapshot_engine=(
                FakeSnapshotEngine()
            ),
            model_registry=(
                FakeRegistry()
            ),
        )

    def test_builds_context(self):
        context = self.build()

        self.assertEqual(
            context.match_id,
            123,
        )
        self.assertEqual(
            context.predicted_winner,
            "Alpha",
        )
        self.assertEqual(
            context.model_version,
            "transparent-v3.3",
        )
        self.assertEqual(
            context.player_a_history_matches,
            40,
        )
        self.assertEqual(
            context.player_b_history_matches,
            35,
        )

    def test_contributions_are_display_ready(self):
        context = self.build()
        contribution = (
            context.contributions[0]
        )

        self.assertEqual(
            contribution["label"],
            "Scoring Power",
        )
        self.assertEqual(
            contribution["direction"],
            "player_a",
        )
        self.assertEqual(
            contribution["impact_percent"],
            11.2,
        )

    def test_converts_to_legacy_opportunity(self):
        context = self.build()

        opportunity = (
            context_to_opportunity(
                context,
                tournament="MODUS",
            )
        )

        self.assertEqual(
            opportunity["selection"],
            "Alpha",
        )
        self.assertEqual(
            opportunity["probability"],
            61.2,
        )
        self.assertEqual(
            opportunity["fair_odds"],
            1.63,
        )
        self.assertEqual(
            opportunity[
                "player_b_history_matches"
            ],
            35,
        )

    def test_summary_is_json_ready(self):
        payload = context_summary(
            self.build()
        )

        self.assertIsInstance(
            payload["contributions"],
            list,
        )
        self.assertIsInstance(
            payload["explanations"],
            list,
        )


if __name__ == "__main__":
    unittest.main()
