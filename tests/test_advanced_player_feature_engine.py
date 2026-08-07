import unittest
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from app.services.advanced_player_feature_engine import (
    AdvancedPlayerFeatureEngine,
)


def performance(**changes):
    values = dict(
        won_match=None,
        threw_first=None,
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
        observed_at=None,
    )
    values.update(changes)
    return SimpleNamespace(**values)


class AdvancedPlayerFeatureEngineTests(unittest.TestCase):
    def test_builds_windows_trends_and_splits(self):
        now = datetime(2026, 8, 5, 12, 0)

        rows = [
            (
                performance(
                    won_match=True,
                    threw_first=True,
                    legs_won=4,
                    legs_lost=3,
                    three_dart_average=96.0,
                    scores_100_plus=12,
                    scores_140_plus=5,
                    scores_180=2,
                    checkout_attempts=8,
                    checkouts_completed=4,
                    highest_checkout=120,
                    observed_at=now,
                ),
                SimpleNamespace(
                    id=10,
                    date=date(2026, 8, 5),
                ),
            ),
            (
                performance(
                    won_match=False,
                    threw_first=False,
                    legs_won=2,
                    legs_lost=4,
                    three_dart_average=88.0,
                    scores_100_plus=8,
                    scores_140_plus=3,
                    scores_180=0,
                    checkout_attempts=6,
                    checkouts_completed=2,
                    highest_checkout=80,
                    observed_at=now - timedelta(hours=2),
                ),
                SimpleNamespace(
                    id=9,
                    date=date(2026, 8, 5),
                ),
            ),
            (
                performance(
                    won_match=True,
                    threw_first=False,
                    legs_won=4,
                    legs_lost=1,
                    three_dart_average=84.0,
                    scores_100_plus=7,
                    scores_140_plus=2,
                    scores_180=1,
                    checkout_attempts=5,
                    checkouts_completed=4,
                    highest_checkout=100,
                    observed_at=now - timedelta(days=2),
                ),
                SimpleNamespace(
                    id=8,
                    date=date(2026, 8, 3),
                ),
            ),
        ]

        profile = (
            AdvancedPlayerFeatureEngine()
            .build_from_rows(
                player_id=1,
                rows=rows,
            )
        )

        last_5 = profile.windows["last_5"]

        self.assertEqual(profile.matches_available, 3)
        self.assertEqual(last_5.matches, 3)
        self.assertEqual(last_5.wins, 2)
        self.assertEqual(last_5.legs_played, 18)
        self.assertEqual(last_5.deciding_matches, 1)
        self.assertEqual(last_5.deciding_wins, 1)
        self.assertEqual(last_5.threw_first_matches, 1)
        self.assertEqual(last_5.threw_second_matches, 2)
        self.assertEqual(
            last_5.checkout_percentage,
            52.632,
        )
        self.assertEqual(
            profile.fatigue.matches_on_latest_day,
            2,
        )
        self.assertEqual(
            profile.fatigue.hours_since_previous_match,
            2.0,
        )

    def test_trend_direction(self):
        trend = (
            AdvancedPlayerFeatureEngine
            ._trend(
                "average",
                95.0,
                90.0,
            )
        )

        self.assertEqual(
            trend.direction,
            "improving",
        )
        self.assertEqual(
            trend.absolute_change,
            5.0,
        )

    def test_empty_profile(self):
        profile = (
            AdvancedPlayerFeatureEngine()
            .build_from_rows(
                player_id=9,
                rows=[],
            )
        )

        self.assertEqual(
            profile.matches_available,
            0,
        )
        self.assertEqual(
            profile.windows["career"].matches,
            0,
        )
        self.assertEqual(
            profile.fatigue.matches_on_latest_day,
            0,
        )


if __name__ == "__main__":
    unittest.main()
