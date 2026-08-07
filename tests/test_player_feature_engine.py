import unittest
from datetime import date
from types import SimpleNamespace

from app.services.player_feature_engine import PlayerFeatureEngine


def performance(**kwargs):
    defaults = dict(
        won_match=None,
        legs_won=None,
        legs_lost=None,
        three_dart_average=None,
        first_nine_average=None,
        scores_100_plus=None,
        scores_140_plus=None,
        scores_180=None,
        checkout_attempts=None,
        checkouts_completed=None,
        checkout_percentage=None,
        highest_checkout=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
    def join(self, *args, **kwargs):
        return self
    def filter(self, *args, **kwargs):
        return self
    def order_by(self, *args, **kwargs):
        return self
    def all(self):
        return self.rows


class FakeDb:
    def __init__(self, rows):
        self.rows = rows
    def query(self, *models):
        return FakeQuery(self.rows)


class PlayerFeatureEngineTests(unittest.TestCase):
    def test_builds_rolling_windows(self):
        rows = [
            (
                performance(
                    won_match=True,
                    legs_won=4,
                    legs_lost=2,
                    three_dart_average=94.0,
                    scores_140_plus=5,
                    scores_180=2,
                    checkout_attempts=8,
                    checkouts_completed=4,
                    checkout_percentage=50.0,
                    highest_checkout=120,
                ),
                SimpleNamespace(id=10, date=date(2026, 8, 5)),
            ),
            (
                performance(
                    won_match=False,
                    legs_won=2,
                    legs_lost=4,
                    three_dart_average=88.0,
                    scores_140_plus=3,
                    scores_180=0,
                    checkout_attempts=6,
                    checkouts_completed=2,
                    checkout_percentage=33.333,
                    highest_checkout=80,
                ),
                SimpleNamespace(id=9, date=date(2026, 8, 4)),
            ),
        ]

        profile = PlayerFeatureEngine().build_player_profile(
            FakeDb(rows), 1, windows=(5, 10)
        )

        self.assertEqual(profile.matches_available, 2)
        self.assertEqual(profile.recent_form, ("W", "L"))
        self.assertEqual(profile.momentum_score, 55.556)

        window = profile.windows[5]
        self.assertEqual(window.matches, 2)
        self.assertEqual(window.win_percentage, 50.0)
        self.assertEqual(window.leg_difference, 0)
        self.assertEqual(window.average_three_dart_average, 91.0)
        self.assertEqual(window.scores_180_per_match, 1.0)
        self.assertEqual(window.calculated_checkout_percentage, 42.857)

    def test_missing_checkout_rows_are_excluded(self):
        rows = [(
            performance(
                won_match=True,
                legs_won=4,
                legs_lost=1,
                three_dart_average=92.0,
                scores_140_plus=4,
                scores_180=1,
                highest_checkout=100,
            ),
            SimpleNamespace(id=1, date=date(2026, 8, 5)),
        )]

        profile = PlayerFeatureEngine().build_player_profile(
            FakeDb(rows), 1, windows=(5,)
        )
        window = profile.windows[5]
        self.assertEqual(window.checkout_data_matches, 0)
        self.assertIsNone(window.calculated_checkout_percentage)
        self.assertEqual(window.highest_checkout, 100)

    def test_empty_player_profile(self):
        profile = PlayerFeatureEngine().build_player_profile(
            FakeDb([]), 99, windows=(5,)
        )
        self.assertEqual(profile.matches_available, 0)
        self.assertEqual(profile.confidence_score, 0.0)
        self.assertIsNone(profile.momentum_score)
        self.assertEqual(profile.windows[5].matches, 0)


if __name__ == "__main__":
    unittest.main()
