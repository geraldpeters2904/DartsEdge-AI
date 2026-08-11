import unittest
from types import SimpleNamespace

from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)
from app.services.transparent_prediction_engine_v33_dual_low_history import (
    TransparentPredictionEngineV33DualLowHistory,
)


def player(
    *,
    name,
    matches_available,
    overall_rating=100.0,
    scoring_rating=100.0,
    finishing_rating=100.0,
    maximums_rating=100.0,
    form_rating=100.0,
    confidence_score=80.0,
    win_percentage=50.0,
    deciding_win_percentage=50.0,
    scoring_stddev=5.0,
):
    return SimpleNamespace(
        player_name=name,
        overall_rating=overall_rating,
        scoring_rating=scoring_rating,
        finishing_rating=finishing_rating,
        maximums_rating=maximums_rating,
        form_rating=form_rating,
        confidence_score=confidence_score,
        advanced_features=SimpleNamespace(
            matches_available=matches_available,
            windows={
                "last_5": SimpleNamespace(
                    win_percentage=win_percentage,
                ),
                "last_20": SimpleNamespace(
                    deciding_win_percentage=(
                        deciding_win_percentage
                    ),
                ),
            },
            trends=(),
            consistency=SimpleNamespace(
                three_dart_average_stddev=scoring_stddev,
            ),
        ),
    )


def snapshot(
    *,
    history_a,
    history_b,
):
    return SimpleNamespace(
        match_id=1,
        player_a=player(
            name="Player A",
            matches_available=history_a,
            scoring_rating=120.0,
            finishing_rating=115.0,
            maximums_rating=110.0,
            win_percentage=80.0,
            deciding_win_percentage=65.0,
            scoring_stddev=4.0,
        ),
        player_b=player(
            name="Player B",
            matches_available=history_b,
            scoring_rating=100.0,
            finishing_rating=100.0,
            maximums_rating=100.0,
            win_percentage=40.0,
            deciding_win_percentage=45.0,
            scoring_stddev=6.0,
        ),
    )


class TransparentPredictionEngineV33DualLowHistoryTests(
    unittest.TestCase
):
    def test_both_low_history_zero_multiplier_removes_recent_win_rate(self):
        snap = snapshot(
            history_a=2,
            history_b=1,
        )

        baseline = (
            TransparentPredictionEngineV33()
            .predict(snap)
        )

        challenger = (
            TransparentPredictionEngineV33DualLowHistory(
                recent_win_rate_multiplier=0.0,
                history_threshold=3,
            )
            .predict(snap)
        )

        baseline_recent = next(
            item
            for item in baseline.contributions
            if item.feature_name == "recent_win_rate"
        )

        challenger_recent = next(
            item
            for item in challenger.contributions
            if item.feature_name == "recent_win_rate"
        )

        self.assertNotEqual(
            baseline_recent.weighted_score,
            0.0,
        )

        self.assertEqual(
            challenger_recent.weighted_score,
            0.0,
        )

        self.assertNotEqual(
            challenger.model_score,
            baseline.model_score,
        )

    def test_only_one_low_history_player_keeps_baseline(self):
        snap = snapshot(
            history_a=2,
            history_b=10,
        )

        baseline = (
            TransparentPredictionEngineV33()
            .predict(snap)
        )

        challenger = (
            TransparentPredictionEngineV33DualLowHistory(
                recent_win_rate_multiplier=0.0,
                history_threshold=3,
            )
            .predict(snap)
        )

        self.assertEqual(
            challenger.player_a_probability,
            baseline.player_a_probability,
        )

        self.assertEqual(
            challenger.player_b_probability,
            baseline.player_b_probability,
        )

        self.assertEqual(
            challenger.model_score,
            baseline.model_score,
        )

    def test_both_three_or_more_keeps_baseline(self):
        snap = snapshot(
            history_a=3,
            history_b=5,
        )

        baseline = (
            TransparentPredictionEngineV33()
            .predict(snap)
        )

        challenger = (
            TransparentPredictionEngineV33DualLowHistory(
                recent_win_rate_multiplier=0.0,
                history_threshold=3,
            )
            .predict(snap)
        )

        self.assertEqual(
            challenger.player_a_probability,
            baseline.player_a_probability,
        )

        self.assertEqual(
            challenger.model_score,
            baseline.model_score,
        )

    def test_half_multiplier_halves_recent_win_rate_when_both_low(self):
        snap = snapshot(
            history_a=1,
            history_b=2,
        )

        baseline = (
            TransparentPredictionEngineV33()
            .predict(snap)
        )

        challenger = (
            TransparentPredictionEngineV33DualLowHistory(
                recent_win_rate_multiplier=0.5,
                history_threshold=3,
            )
            .predict(snap)
        )

        baseline_recent = next(
            item
            for item in baseline.contributions
            if item.feature_name == "recent_win_rate"
        )

        challenger_recent = next(
            item
            for item in challenger.contributions
            if item.feature_name == "recent_win_rate"
        )

        self.assertAlmostEqual(
            challenger_recent.weighted_score,
            baseline_recent.weighted_score * 0.5,
            places=6,
        )

    def test_other_features_are_unchanged_when_both_low(self):
        snap = snapshot(
            history_a=1,
            history_b=2,
        )

        baseline = (
            TransparentPredictionEngineV33()
            .predict(snap)
        )

        challenger = (
            TransparentPredictionEngineV33DualLowHistory(
                recent_win_rate_multiplier=0.25,
                history_threshold=3,
            )
            .predict(snap)
        )

        baseline_map = {
            item.feature_name: item
            for item in baseline.contributions
        }

        challenger_map = {
            item.feature_name: item
            for item in challenger.contributions
        }

        for feature_name in baseline_map:
            if feature_name == "recent_win_rate":
                continue

            self.assertEqual(
                challenger_map[feature_name].weighted_score,
                baseline_map[feature_name].weighted_score,
            )

    def test_rejects_negative_multiplier(self):
        with self.assertRaisesRegex(
            ValueError,
            "cannot be negative",
        ):
            TransparentPredictionEngineV33DualLowHistory(
                recent_win_rate_multiplier=-0.1,
            )

    def test_rejects_multiplier_above_one(self):
        with self.assertRaisesRegex(
            ValueError,
            "cannot exceed",
        ):
            TransparentPredictionEngineV33DualLowHistory(
                recent_win_rate_multiplier=1.1,
            )

    def test_rejects_invalid_history_threshold(self):
        with self.assertRaisesRegex(
            ValueError,
            "greater than zero",
        ):
            TransparentPredictionEngineV33DualLowHistory(
                history_threshold=0,
            )


if __name__ == "__main__":
    unittest.main()
