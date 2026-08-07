import unittest
from types import SimpleNamespace

from app.services.feature_explorer_service import (
    FeatureExplorerService,
)


class FeatureExplorerServiceTests(unittest.TestCase):
    def test_builds_compact_report(self):
        window = SimpleNamespace(
            label="last_5",
            matches=5,
            wins=3,
            losses=2,
            win_percentage=60.0,
            average_three_dart_average=92.0,
            checkout_percentage=40.0,
            scores_180_per_match=1.2,
            scores_180_per_leg=0.2,
            leg_difference=4,
            deciding_win_percentage=66.667,
            threw_first_win_percentage=75.0,
            threw_second_win_percentage=50.0,
        )

        profile = SimpleNamespace(
            competition_code=None,
            matches_available=25,
            latest_match_id=100,
            latest_match_date="2026-08-05",
            windows={
                "last_5": window,
                "last_10": window,
                "last_20": window,
                "last_50": window,
                "career": window,
            },
            trends=(),
            fatigue=SimpleNamespace(
                matches_on_latest_day=3,
                legs_on_latest_day=18,
                hours_since_previous_match=2.0,
                days_since_previous_match=1,
            ),
        )

        report = (
            FeatureExplorerService
            ._build_report(
                player_id=1,
                player_name="Example Player",
                profile=profile,
            )
        )

        self.assertEqual(
            report.player_name,
            "Example Player",
        )
        self.assertEqual(
            len(report.windows),
            5,
        )
        self.assertEqual(
            report.windows[0].win_percentage,
            60.0,
        )
        self.assertEqual(
            report.matches_on_latest_day,
            3,
        )


if __name__ == "__main__":
    unittest.main()
