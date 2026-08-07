import unittest
from types import SimpleNamespace

from app.services.player_rating_engine import (
    PlayerRatingEngine,
)


class FakeQuery:
    def __init__(self, player):
        self.player = player

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.player


class FakeDb:
    def __init__(self, player):
        self.player = player

    def query(self, *models):
        return FakeQuery(self.player)


def window(
    *,
    win_percentage,
    scoring_power,
    finishing_power,
    scores_180_per_match,
    average_consistency,
    legs_won,
    legs_lost,
):
    return SimpleNamespace(
        win_percentage=win_percentage,
        scoring_power=scoring_power,
        finishing_power=finishing_power,
        scores_180_per_match=scores_180_per_match,
        average_consistency=average_consistency,
        legs_won=legs_won,
        legs_lost=legs_lost,
    )


class FakeFeatureEngine:
    def __init__(self, profile):
        self.profile = profile

    def build_player_profile(
        self,
        db,
        player_id,
        *,
        competition_code=None,
    ):
        return self.profile


class PlayerRatingEngineTests(unittest.TestCase):
    def setUp(self):
        self.profile = SimpleNamespace(
            matches_available=20,
            latest_match_id=100,
            latest_match_date="2026-08-05",
            momentum_score=80.0,
            confidence_score=100.0,
            windows={
                5: window(
                    win_percentage=80.0,
                    scoring_power=75.0,
                    finishing_power=65.0,
                    scores_180_per_match=2.0,
                    average_consistency=90.0,
                    legs_won=20,
                    legs_lost=10,
                ),
                10: window(
                    win_percentage=70.0,
                    scoring_power=70.0,
                    finishing_power=60.0,
                    scores_180_per_match=1.5,
                    average_consistency=85.0,
                    legs_won=36,
                    legs_lost=24,
                ),
                20: window(
                    win_percentage=60.0,
                    scoring_power=65.0,
                    finishing_power=55.0,
                    scores_180_per_match=1.0,
                    average_consistency=80.0,
                    legs_won=65,
                    legs_lost=55,
                ),
            },
        )

        self.engine = PlayerRatingEngine(
            feature_engine=FakeFeatureEngine(
                self.profile
            )
        )

    def test_builds_multi_dimensional_rating(self):
        db = FakeDb(
            SimpleNamespace(
                id=1,
                name="Example Player",
            )
        )

        rating = self.engine.build_player_rating(
            db,
            1,
        )

        self.assertEqual(
            rating.player_name,
            "Example Player",
        )
        self.assertGreater(
            rating.overall_rating,
            1500,
        )
        self.assertGreater(
            rating.scoring_rating,
            1500,
        )
        self.assertGreater(
            rating.form_rating,
            1500,
        )
        self.assertEqual(
            rating.confidence_score,
            100.0,
        )

    def test_low_confidence_shrinks_towards_base(self):
        profile = SimpleNamespace(
            **{
                **self.profile.__dict__,
                "confidence_score": 10.0,
            }
        )

        engine = PlayerRatingEngine(
            feature_engine=FakeFeatureEngine(
                profile
            )
        )

        rating = engine.build_player_rating(
            FakeDb(
                SimpleNamespace(
                    id=1,
                    name="Example Player",
                )
            ),
            1,
        )

        self.assertLess(
            abs(rating.overall_rating - 1500),
            100,
        )

    def test_unknown_player_raises(self):
        with self.assertRaisesRegex(
            ValueError,
            "was not found",
        ):
            self.engine.build_player_rating(
                FakeDb(None),
                999,
            )

    def test_compare_players_returns_edges(self):
        strong = self.engine.build_player_rating(
            FakeDb(
                SimpleNamespace(
                    id=1,
                    name="Strong Player",
                )
            ),
            1,
        )

        weak_profile = SimpleNamespace(
            **{
                **self.profile.__dict__,
                "momentum_score": 20.0,
                "windows": {
                    5: window(
                        win_percentage=20.0,
                        scoring_power=35.0,
                        finishing_power=30.0,
                        scores_180_per_match=0.2,
                        average_consistency=60.0,
                        legs_won=8,
                        legs_lost=20,
                    ),
                    10: window(
                        win_percentage=30.0,
                        scoring_power=40.0,
                        finishing_power=35.0,
                        scores_180_per_match=0.4,
                        average_consistency=65.0,
                        legs_won=18,
                        legs_lost=32,
                    ),
                    20: window(
                        win_percentage=35.0,
                        scoring_power=45.0,
                        finishing_power=40.0,
                        scores_180_per_match=0.5,
                        average_consistency=70.0,
                        legs_won=40,
                        legs_lost=60,
                    ),
                },
            }
        )

        class DualFeatureEngine:
            def build_player_profile(
                self,
                db,
                player_id,
                *,
                competition_code=None,
            ):
                return (
                    self.profile_a
                    if player_id == 1
                    else self.profile_b
                )

        dual = DualFeatureEngine()
        dual.profile_a = self.profile
        dual.profile_b = weak_profile

        engine = PlayerRatingEngine(
            feature_engine=dual
        )

        class DualDb:
            def query(self, *models):
                class Query:
                    def __init__(self):
                        self.player_id = None
                    def filter(self, expression):
                        self.player_id = (
                            getattr(
                                expression.right,
                                "value",
                                None,
                            )
                        )
                        return self
                    def first(self):
                        if self.player_id == 1:
                            return SimpleNamespace(
                                id=1,
                                name="Strong Player",
                            )
                        return SimpleNamespace(
                            id=2,
                            name="Weak Player",
                        )
                return Query()

        comparison = engine.compare_players(
            DualDb(),
            1,
            2,
        )

        self.assertGreater(
            comparison["edges"]["overall"],
            0,
        )
        self.assertGreater(
            comparison["edges"]["scoring"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
