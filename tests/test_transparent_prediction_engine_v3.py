import unittest
from types import SimpleNamespace

from app.services.transparent_prediction_engine_v3 import (
    TransparentPredictionEngineV3,
)
from app.services.transparent_v3_features import NumericEdgeFeature


def player(name, rating):
    return SimpleNamespace(
        player_name=name,
        overall_rating=rating,
        form_rating=rating,
        scoring_rating=rating,
        finishing_rating=rating,
        maximums_rating=rating,
        confidence_score=90.0,
        advanced_features=SimpleNamespace(
            windows={
                "last_5": SimpleNamespace(win_percentage=50.0),
                "last_20": SimpleNamespace(deciding_win_percentage=50.0),
            },
            trends=(),
        ),
    )


class TransparentPredictionEngineV3Tests(unittest.TestCase):
    def test_plugin_feature_drives_prediction(self):
        feature = NumericEdgeFeature(
            name="test_feature",
            weight=1.0,
            scale=100.0,
            edge_getter=lambda s: (
                s.player_a.overall_rating
                - s.player_b.overall_rating
            ),
            label="test strength",
        )
        snapshot = SimpleNamespace(
            match_id=1,
            player_a=player("A", 1600),
            player_b=player("B", 1500),
        )

        prediction = TransparentPredictionEngineV3(
            features=(feature,)
        ).predict(snapshot)

        self.assertGreater(prediction.player_a_probability, 50.0)
        self.assertEqual(prediction.predicted_winner, "A")
        self.assertEqual(
            prediction.contributions[0].feature_name,
            "test_feature",
        )

    def test_feature_can_be_disabled(self):
        reduced = TransparentPredictionEngineV3().without_features(
            "checkout_trend"
        )
        self.assertNotIn(
            "checkout_trend",
            reduced.feature_names(),
        )

    def test_feature_weight_can_be_changed(self):
        changed = TransparentPredictionEngineV3().with_feature_weight(
            "recent_form",
            0.50,
        )
        selected = next(
            feature for feature in changed.features
            if feature.name == "recent_form"
        )
        self.assertEqual(selected.weight, 0.50)


if __name__ == "__main__":
    unittest.main()
