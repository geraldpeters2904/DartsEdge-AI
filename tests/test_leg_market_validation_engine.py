import unittest

from datetime import date
from types import SimpleNamespace

from app.services.leg_market_validation_engine import (
    LegMarketValidationEngine,
)


class FakeMatchQuery:
    def __init__(self, matches):
        self.matches = matches

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return self.matches


class FakeDb:
    def __init__(self, matches):
        self.matches = matches

    def query(self, *models):
        return FakeMatchQuery(self.matches)


class FakeSnapshotEngine:
    def build_match_snapshot(
        self,
        db,
        match_id,
        *,
        competition_code=None,
    ):
        return SimpleNamespace(
            match_id=match_id,
            player_a=SimpleNamespace(
                last_10_average=90.0,
                last_10_checkout_percentage=40.0,
                last_10_matches=10,
                latest_match_date="2026-07-30",
            ),
            player_b=SimpleNamespace(
                last_10_average=90.0,
                last_10_checkout_percentage=40.0,
                last_10_matches=10,
                latest_match_date="2026-07-29",
            ),
        )


class LegMarketValidationEngineTests(unittest.TestCase):
    def test_validates_handicap_and_total_legs_from_pre_match_snapshot(self):
        match = SimpleNamespace(
            id=1,
            date=date(2026, 8, 1),
            tournament="MODUS",
            stage="Group A",
            status="completed",
            player_a="Player A",
            player_b="Player B",
            winner="Player A",
            score="4-2",
            match_format="Best of 7",
        )

        engine = LegMarketValidationEngine(
            snapshot_engine=FakeSnapshotEngine(),
        )

        report = engine.validate_matches(
            FakeDb([match]),
            handicap_line=-1.5,
            total_legs_line=5.5,
        )

        self.assertEqual(report.matches_considered, 1)
        self.assertEqual(report.matches_evaluated, 1)
        self.assertEqual(report.matches_skipped, 0)
        self.assertEqual(len(report.records), 1)

        record = report.records[0]

        self.assertAlmostEqual(
            record.player_a_leg_win_probability,
            0.5,
            places=6,
        )
        self.assertEqual(record.player_a_average, 90.0)
        self.assertEqual(record.player_a_checkout, 40.0)
        self.assertEqual(record.player_b_average, 90.0)
        self.assertEqual(record.player_b_checkout, 40.0)
        self.assertEqual(record.best_of, 7)
        self.assertEqual(record.match_date, match.date)
        self.assertEqual(
            record.player_a_latest_match_date,
            "2026-07-30",
        )
        self.assertEqual(
            record.player_b_latest_match_date,
            "2026-07-29",
        )
        self.assertAlmostEqual(
            record.player_a_handicap_probability,
            0.34375,
            places=6,
        )
        self.assertEqual(
            record.player_a_handicap_result,
            1,
        )
        self.assertAlmostEqual(
            record.total_legs_over_probability,
            0.625,
            places=6,
        )
        self.assertEqual(
            record.total_legs_over_result,
            1,
        )


class LegMarketCalibrationTests(unittest.TestCase):
    def test_report_includes_brier_scores_and_calibration(self):
        matches = [
            SimpleNamespace(
                id=1,
                date=date(2026, 8, 1),
                tournament="MODUS",
                stage="Group A",
                status="completed",
                player_a="Player A",
                player_b="Player B",
                winner="Player A",
                score="4-2",
                match_format="Best of 7",
            ),
            SimpleNamespace(
                id=2,
                date=date(2026, 8, 2),
                tournament="MODUS",
                stage="Group A",
                status="completed",
                player_a="Player C",
                player_b="Player D",
                winner="Player D",
                score="2-4",
                match_format="Best of 7",
            ),
        ]

        engine = LegMarketValidationEngine(
            snapshot_engine=FakeSnapshotEngine(),
        )

        report = engine.validate_matches(
            FakeDb(matches),
            handicap_line=-1.5,
            total_legs_line=5.5,
        )

        self.assertAlmostEqual(
            report.handicap_brier_score,
            (
                (0.34375 - 1) ** 2
                + (0.34375 - 0) ** 2
            ) / 2,
            places=6,
        )
        self.assertAlmostEqual(
            report.total_legs_brier_score,
            (0.625 - 1) ** 2,
            places=6,
        )

        handicap_bucket = next(
            bucket
            for bucket in report.handicap_calibration
            if bucket.lower_bound == 30
        )
        self.assertEqual(handicap_bucket.predictions, 2)
        self.assertAlmostEqual(
            handicap_bucket.mean_probability,
            34.375,
            places=3,
        )
        self.assertEqual(
            handicap_bucket.observed_hit_rate,
            50.0,
        )

        total_bucket = next(
            bucket
            for bucket in report.total_legs_calibration
            if bucket.lower_bound == 60
        )
        self.assertEqual(total_bucket.predictions, 2)
        self.assertAlmostEqual(
            total_bucket.mean_probability,
            62.5,
            places=3,
        )
        self.assertEqual(
            total_bucket.observed_hit_rate,
            100.0,
        )


if __name__ == "__main__":
    unittest.main()
