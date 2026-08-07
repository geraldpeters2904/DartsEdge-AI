import unittest
from types import SimpleNamespace

from app.services.transparent_prediction_engine import (
    TransparentPredictionEngine,
)


def snapshot(
    *,
    overall,
    form,
    scoring,
    finishing,
    maximums,
    momentum,
    confidence_a=90.0,
    confidence_b=90.0,
):
    return SimpleNamespace(
        match_id=100,
        overall_edge=overall,
        form_edge=form,
        scoring_edge=scoring,
        finishing_edge=finishing,
        maximums_edge=maximums,
        momentum_edge=momentum,
        player_a=SimpleNamespace(
            player_name="Player A",
            confidence_score=confidence_a,
        ),
        player_b=SimpleNamespace(
            player_name="Player B",
            confidence_score=confidence_b,
        ),
    )


class TransparentPredictionEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = TransparentPredictionEngine()

    def test_positive_edges_favour_player_a(self):
        prediction = self.engine.predict(
            snapshot(
                overall=80,
                form=60,
                scoring=50,
                finishing=20,
                maximums=30,
                momentum=15,
            )
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
            round(
                prediction.player_a_probability
                + prediction.player_b_probability,
                3,
            ),
            100.0,
        )

    def test_negative_edges_favour_player_b(self):
        prediction = self.engine.predict(
            snapshot(
                overall=-80,
                form=-60,
                scoring=-50,
                finishing=-20,
                maximums=-30,
                momentum=-15,
            )
        )

        self.assertLess(
            prediction.player_a_probability,
            50.0,
        )
        self.assertEqual(
            prediction.predicted_winner,
            "Player B",
        )

    def test_even_snapshot_returns_fifty_fifty(self):
        prediction = self.engine.predict(
            snapshot(
                overall=0,
                form=0,
                scoring=0,
                finishing=0,
                maximums=0,
                momentum=None,
            )
        )

        self.assertEqual(
            prediction.player_a_probability,
            50.0,
        )
        self.assertEqual(
            prediction.player_b_probability,
            50.0,
        )

    def test_low_data_confidence_reduces_prediction_confidence(self):
        strong_data = self.engine.predict(
            snapshot(
                overall=80,
                form=50,
                scoring=40,
                finishing=20,
                maximums=10,
                momentum=10,
                confidence_a=100,
                confidence_b=100,
            )
        )
        weak_data = self.engine.predict(
            snapshot(
                overall=80,
                form=50,
                scoring=40,
                finishing=20,
                maximums=10,
                momentum=10,
                confidence_a=20,
                confidence_b=20,
            )
        )

        self.assertLess(
            weak_data.confidence,
            strong_data.confidence,
        )

    def test_custom_weights_are_normalised(self):
        engine = TransparentPredictionEngine(
            weights={
                "overall": 2.0,
                "form": 1.0,
            }
        )

        self.assertAlmostEqual(
            engine.weights["overall"],
            2 / 3,
        )
        self.assertAlmostEqual(
            engine.weights["form"],
            1 / 3,
        )
        self.assertEqual(
            engine.weights["scoring"],
            0.0,
        )

    def test_unknown_weight_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unknown prediction weight",
        ):
            TransparentPredictionEngine(
                weights={
                    "overall": 1.0,
                    "mystery": 1.0,
                }
            )


if __name__ == "__main__":
    unittest.main()
