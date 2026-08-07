import unittest
from types import SimpleNamespace

from app.services.transparent_prediction_engine_v2 import (
    AdvancedMatchPredictionInput,
    AdvancedPlayerPredictionInput,
    TransparentPredictionEngineV2,
)


def advanced(
    *,
    last5_win,
    avg_trend,
    checkout_trend,
    maximums_trend,
    deciding,
    score_140_leg,
    score_180_leg,
):
    return SimpleNamespace(
        windows={
            "last_5": SimpleNamespace(
                win_percentage=last5_win,
            ),
            "last_20": SimpleNamespace(
                deciding_win_percentage=deciding,
                scores_140_plus_per_leg=score_140_leg,
                scores_180_per_leg=score_180_leg,
            ),
        },
        trends=(
            SimpleNamespace(
                metric="three_dart_average",
                absolute_change=avg_trend,
            ),
            SimpleNamespace(
                metric="checkout_percentage",
                absolute_change=checkout_trend,
            ),
            SimpleNamespace(
                metric="scores_180_per_match",
                absolute_change=maximums_trend,
            ),
        ),
    )


def player(
    name,
    *,
    overall,
    form,
    scoring,
    finishing,
    maximums,
    confidence,
    features,
):
    return AdvancedPlayerPredictionInput(
        player_id=1,
        player_name=name,
        overall_rating=overall,
        scoring_rating=scoring,
        finishing_rating=finishing,
        maximums_rating=maximums,
        form_rating=form,
        confidence_score=confidence,
        advanced_features=features,
    )


class TransparentPredictionEngineV2Tests(unittest.TestCase):
    def test_advanced_edges_favour_stronger_player(self):
        snapshot = AdvancedMatchPredictionInput(
            match_id=1,
            player_a=player(
                "Player A",
                overall=1600,
                form=1620,
                scoring=1610,
                finishing=1580,
                maximums=1600,
                confidence=90,
                features=advanced(
                    last5_win=80,
                    avg_trend=4,
                    checkout_trend=5,
                    maximums_trend=0.5,
                    deciding=70,
                    score_140_leg=0.8,
                    score_180_leg=0.2,
                ),
            ),
            player_b=player(
                "Player B",
                overall=1500,
                form=1480,
                scoring=1490,
                finishing=1500,
                maximums=1490,
                confidence=90,
                features=advanced(
                    last5_win=30,
                    avg_trend=-2,
                    checkout_trend=-4,
                    maximums_trend=-0.2,
                    deciding=40,
                    score_140_leg=0.5,
                    score_180_leg=0.1,
                ),
            ),
        )

        prediction = TransparentPredictionEngineV2().predict(
            snapshot
        )

        self.assertGreater(
            prediction.player_a_probability,
            50.0,
        )
        self.assertEqual(
            prediction.predicted_winner,
            "Player A",
        )
        self.assertEqual(
            prediction.model_version,
            "transparent-v2",
        )

    def test_even_inputs_return_fifty_fifty(self):
        features = advanced(
            last5_win=50,
            avg_trend=0,
            checkout_trend=0,
            maximums_trend=0,
            deciding=50,
            score_140_leg=0.5,
            score_180_leg=0.1,
        )
        snapshot = AdvancedMatchPredictionInput(
            match_id=2,
            player_a=player(
                "A",
                overall=1500,
                form=1500,
                scoring=1500,
                finishing=1500,
                maximums=1500,
                confidence=100,
                features=features,
            ),
            player_b=player(
                "B",
                overall=1500,
                form=1500,
                scoring=1500,
                finishing=1500,
                maximums=1500,
                confidence=100,
                features=features,
            ),
        )

        prediction = TransparentPredictionEngineV2().predict(
            snapshot
        )

        self.assertEqual(
            prediction.player_a_probability,
            50.0,
        )
        self.assertEqual(
            prediction.player_b_probability,
            50.0,
        )


if __name__ == "__main__":
    unittest.main()
