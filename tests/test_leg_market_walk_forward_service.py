import unittest

from app.services.leg_market_validation_engine import (
    LegMarketValidationRecord,
)
from app.services.leg_market_walk_forward_service import (
    brier_score,
    chronological_folds,
    fit_platt_calibration,
)


def record(match_id):
    return LegMarketValidationRecord(
        match_id=match_id,
        player_a_leg_win_probability=0.5,
        player_a_handicap_probability=0.4,
        player_a_handicap_result=0,
        total_legs_over_probability=0.6,
        total_legs_over_result=1,
    )


class ChronologicalFoldTests(unittest.TestCase):
    def test_builds_expanding_window_folds(self):
        records = tuple(
            record(match_id)
            for match_id in range(1, 11)
        )

        folds = chronological_folds(
            records,
            initial_train_size=4,
            test_size=2,
        )

        self.assertEqual(len(folds), 3)

        self.assertEqual(
            [item.match_id for item in folds[0].train],
            [1, 2, 3, 4],
        )
        self.assertEqual(
            [item.match_id for item in folds[0].test],
            [5, 6],
        )

        self.assertEqual(
            [item.match_id for item in folds[1].train],
            [1, 2, 3, 4, 5, 6],
        )
        self.assertEqual(
            [item.match_id for item in folds[1].test],
            [7, 8],
        )

        self.assertEqual(
            [item.match_id for item in folds[2].train],
            [1, 2, 3, 4, 5, 6, 7, 8],
        )
        self.assertEqual(
            [item.match_id for item in folds[2].test],
            [9, 10],
        )

    def test_never_places_future_record_in_training_set(self):
        records = tuple(
            record(match_id)
            for match_id in range(1, 13)
        )

        folds = chronological_folds(
            records,
            initial_train_size=6,
            test_size=2,
        )

        for fold in folds:
            self.assertLess(
                max(item.match_id for item in fold.train),
                min(item.match_id for item in fold.test),
            )

    def test_rejects_invalid_window_sizes(self):
        records = tuple(
            record(match_id)
            for match_id in range(1, 6)
        )

        with self.assertRaises(ValueError):
            chronological_folds(
                records,
                initial_train_size=0,
                test_size=2,
            )

        with self.assertRaises(ValueError):
            chronological_folds(
                records,
                initial_train_size=3,
                test_size=0,
            )




class DateDisjointFoldTests(unittest.TestCase):

    def test_never_splits_calendar_date_between_train_and_test(self):
        from datetime import date

        from app.services.leg_market_walk_forward_service import (
            date_disjoint_folds,
        )

        dates = (
            date(2026, 1, 1),
            date(2026, 1, 1),
            date(2026, 1, 2),
            date(2026, 1, 2),
            date(2026, 1, 2),
            date(2026, 1, 3),
            date(2026, 1, 3),
            date(2026, 1, 4),
            date(2026, 1, 4),
            date(2026, 1, 5),
        )

        records = tuple(
            LegMarketValidationRecord(
                match_id=index,
                player_a_leg_win_probability=0.5,
                player_a_handicap_probability=0.4,
                player_a_handicap_result=0,
                total_legs_over_probability=0.6,
                total_legs_over_result=1,
                match_date=match_date,
            )
            for index, match_date in enumerate(
                dates,
                start=1,
            )
        )

        folds = date_disjoint_folds(
            records,
            initial_train_size=4,
            test_size=2,
        )

        self.assertGreaterEqual(len(folds), 1)

        for fold in folds:
            train_dates = {
                item.match_date
                for item in fold.train
            }
            test_dates = {
                item.match_date
                for item in fold.test
            }

            self.assertTrue(
                train_dates.isdisjoint(test_dates)
            )
            self.assertLess(
                max(train_dates),
                min(test_dates),
            )

    def test_rejects_records_without_match_date(self):
        from app.services.leg_market_walk_forward_service import (
            date_disjoint_folds,
        )

        records = (
            record(1),
            record(2),
            record(3),
        )

        with self.assertRaises(ValueError):
            date_disjoint_folds(
                records,
                initial_train_size=2,
                test_size=1,
            )


class PlattFittingTests(unittest.TestCase):
    def test_brier_score_matches_expected_value(self):
        from app.services.leg_market_walk_forward_service import (
            brier_score,
        )

        score = brier_score(
            probabilities=(0.8, 0.3),
            results=(1, 0),
        )

        self.assertAlmostEqual(
            score,
            ((0.8 - 1) ** 2 + (0.3 - 0) ** 2) / 2,
            places=9,
        )

    def test_fitted_platt_calibration_improves_overconfident_predictions(self):
        from app.services.leg_market_walk_forward_service import (
            brier_score,
            fit_platt_calibration,
        )

        probabilities = (
            0.95,
            0.90,
            0.85,
            0.80,
            0.20,
            0.15,
            0.10,
            0.05,
        )
        results = (
            1,
            0,
            1,
            0,
            1,
            0,
            0,
            0,
        )

        calibration = fit_platt_calibration(
            probabilities,
            results,
        )

        raw_score = brier_score(
            probabilities,
            results,
        )
        calibrated_probabilities = tuple(
            calibration.apply(probability)
            for probability in probabilities
        )
        calibrated_score = brier_score(
            calibrated_probabilities,
            results,
        )

        self.assertLess(
            calibrated_score,
            raw_score,
        )
        self.assertGreaterEqual(
            calibration.slope,
            0.0,
        )

    def test_fitting_rejects_mismatched_inputs(self):
        from app.services.leg_market_walk_forward_service import (
            fit_platt_calibration,
        )

        with self.assertRaises(ValueError):
            fit_platt_calibration(
                probabilities=(0.5, 0.6),
                results=(1,),
            )

    def test_fitting_rejects_empty_inputs(self):
        from app.services.leg_market_walk_forward_service import (
            fit_platt_calibration,
        )

        with self.assertRaises(ValueError):
            fit_platt_calibration(
                probabilities=(),
                results=(),
            )


class WalkForwardEvaluationTests(unittest.TestCase):
    def test_evaluates_handicap_fold_out_of_sample(self):
        from app.services.leg_market_walk_forward_service import (
            evaluate_fold,
        )

        train = tuple(
            LegMarketValidationRecord(
                match_id=index,
                player_a_leg_win_probability=0.5,
                player_a_handicap_probability=probability,
                player_a_handicap_result=result,
                total_legs_over_probability=0.6,
                total_legs_over_result=1,
            )
            for index, (probability, result) in enumerate(
                (
                    (0.90, 1),
                    (0.80, 0),
                    (0.70, 1),
                    (0.30, 0),
                    (0.20, 1),
                    (0.10, 0),
                ),
                start=1,
            )
        )

        test = (
            LegMarketValidationRecord(
                match_id=7,
                player_a_leg_win_probability=0.5,
                player_a_handicap_probability=0.85,
                player_a_handicap_result=1,
                total_legs_over_probability=0.6,
                total_legs_over_result=1,
            ),
            LegMarketValidationRecord(
                match_id=8,
                player_a_leg_win_probability=0.5,
                player_a_handicap_probability=0.15,
                player_a_handicap_result=0,
                total_legs_over_probability=0.6,
                total_legs_over_result=1,
            ),
        )

        result = evaluate_fold(
            train,
            test,
            probability_attr="player_a_handicap_probability",
            result_attr="player_a_handicap_result",
        )

        self.assertEqual(result.train_size, 6)
        self.assertEqual(result.test_size, 2)

        self.assertAlmostEqual(
            result.train_hit_rate,
            0.5,
            places=9,
        )

        self.assertAlmostEqual(
            result.test_hit_rate,
            0.5,
            places=9,
        )

        self.assertAlmostEqual(
            result.raw_brier_score,
            ((0.85 - 1) ** 2 + (0.15 - 0) ** 2) / 2,
            places=9,
        )

        self.assertAlmostEqual(
            result.constant_brier_score,
            ((0.5 - 1) ** 2 + (0.5 - 0) ** 2) / 2,
            places=9,
        )

        self.assertIsNotNone(
            result.calibration,
        )

        self.assertGreaterEqual(
            result.calibrated_brier_score,
            0.0,
        )
        self.assertLessEqual(
            result.calibrated_brier_score,
            1.0,
        )


class FixedHoldoutEvaluationTests(unittest.TestCase):

    def test_fits_calibration_on_train_and_scores_holdout(self):
        from types import SimpleNamespace

        from app.services.leg_market_walk_forward_service import (
            evaluate_fixed_holdout,
        )

        train = tuple(
            SimpleNamespace(
                probability=probability,
                result=result,
            )
            for probability, result in (
                (0.20, 0),
                (0.30, 0),
                (0.40, 0),
                (0.60, 1),
                (0.70, 1),
                (0.80, 1),
            )
        )

        test = tuple(
            SimpleNamespace(
                probability=probability,
                result=result,
            )
            for probability, result in (
                (0.25, 0),
                (0.75, 1),
            )
        )

        evaluation = evaluate_fixed_holdout(
            train,
            test,
            probability_attr="probability",
            result_attr="result",
        )

        self.assertEqual(evaluation.train_size, 6)
        self.assertEqual(evaluation.test_size, 2)

        expected_calibration = fit_platt_calibration(
            tuple(record.probability for record in train),
            tuple(record.result for record in train),
        )

        self.assertEqual(
            evaluation.calibration,
            expected_calibration,
        )

        expected_probabilities = tuple(
            expected_calibration.apply(record.probability)
            for record in test
        )

        self.assertAlmostEqual(
            evaluation.calibrated_brier_score,
            brier_score(
                expected_probabilities,
                tuple(record.result for record in test),
            ),
            places=12,
        )


class DateDisjointWalkForwardEvaluationTests(unittest.TestCase):

    def test_evaluates_date_disjoint_folds(self):
        from datetime import date, timedelta

        from app.services.leg_market_walk_forward_service import (
            evaluate_date_disjoint_walk_forward,
        )

        start = date(2026, 1, 1)

        records = tuple(
            LegMarketValidationRecord(
                match_id=index,
                player_a_leg_win_probability=0.5,
                player_a_handicap_probability=(
                    0.7 if index % 2 else 0.3
                ),
                player_a_handicap_result=(
                    1 if index % 2 else 0
                ),
                total_legs_over_probability=0.6,
                total_legs_over_result=1,
                match_date=(
                    start
                    + timedelta(days=(index - 1) // 2)
                ),
            )
            for index in range(1, 13)
        )

        report = evaluate_date_disjoint_walk_forward(
            records,
            probability_attr="player_a_handicap_probability",
            result_attr="player_a_handicap_result",
            initial_train_size=4,
            test_size=2,
        )

        self.assertEqual(report.records, 12)
        self.assertGreaterEqual(report.folds_evaluated, 1)
        self.assertGreater(report.test_observations, 0)

        self.assertGreaterEqual(
            report.raw_brier_score,
            0.0,
        )
        self.assertLessEqual(
            report.raw_brier_score,
            1.0,
        )

        self.assertGreaterEqual(
            report.calibrated_brier_score,
            0.0,
        )
        self.assertLessEqual(
            report.calibrated_brier_score,
            1.0,
        )


class WalkForwardReportTests(unittest.TestCase):
    def test_evaluates_all_expanding_window_folds(self):
        from app.services.leg_market_walk_forward_service import (
            evaluate_walk_forward,
        )

        probabilities_and_results = (
            (0.90, 1),
            (0.80, 0),
            (0.70, 1),
            (0.60, 0),
            (0.55, 1),
            (0.45, 0),
            (0.40, 1),
            (0.30, 0),
            (0.20, 0),
            (0.10, 0),
        )

        records = tuple(
            LegMarketValidationRecord(
                match_id=index,
                player_a_leg_win_probability=0.5,
                player_a_handicap_probability=probability,
                player_a_handicap_result=result,
                total_legs_over_probability=probability,
                total_legs_over_result=result,
            )
            for index, (probability, result) in enumerate(
                probabilities_and_results,
                start=1,
            )
        )

        report = evaluate_walk_forward(
            records,
            probability_attr="player_a_handicap_probability",
            result_attr="player_a_handicap_result",
            initial_train_size=4,
            test_size=2,
        )

        self.assertEqual(report.records, 10)
        self.assertEqual(report.folds_evaluated, 3)
        self.assertEqual(report.test_observations, 6)
        self.assertEqual(len(report.folds), 3)

        self.assertEqual(
            [fold.train_size for fold in report.folds],
            [4, 6, 8],
        )
        self.assertEqual(
            [fold.test_size for fold in report.folds],
            [2, 2, 2],
        )

        self.assertGreaterEqual(
            report.raw_brier_score,
            0.0,
        )
        self.assertLessEqual(
            report.raw_brier_score,
            1.0,
        )

        self.assertGreaterEqual(
            report.calibrated_brier_score,
            0.0,
        )
        self.assertLessEqual(
            report.calibrated_brier_score,
            1.0,
        )

        self.assertGreaterEqual(
            report.constant_brier_score,
            0.0,
        )
        self.assertLessEqual(
            report.constant_brier_score,
            1.0,
        )

        self.assertEqual(
            len(report.slopes),
            3,
        )
        self.assertEqual(
            len(report.intercepts),
            3,
        )


class FastFitterRegressionTests(unittest.TestCase):
    def test_fast_fitter_matches_exhaustive_grid_on_known_sample(self):
        from app.services.leg_market_calibration_service import (
            PlattCalibration,
        )
        from app.services.leg_market_walk_forward_service import (
            brier_score,
            fit_platt_calibration,
        )

        probabilities = (
            0.95,
            0.90,
            0.85,
            0.80,
            0.20,
            0.15,
            0.10,
            0.05,
        )
        results = (
            1,
            0,
            1,
            0,
            1,
            0,
            0,
            0,
        )

        fitted = fit_platt_calibration(
            probabilities,
            results,
        )

        best = None

        for slope_step in range(0, 81):
            slope = slope_step / 40.0

            for intercept_step in range(-80, 81):
                intercept = intercept_step / 40.0

                calibration = PlattCalibration(
                    slope=slope,
                    intercept=intercept,
                )

                score = brier_score(
                    tuple(
                        calibration.apply(probability)
                        for probability in probabilities
                    ),
                    results,
                )

                candidate = (
                    score,
                    slope,
                    intercept,
                )

                if best is None or candidate < best:
                    best = candidate

        _, expected_slope, expected_intercept = best

        self.assertEqual(
            fitted.slope,
            expected_slope,
        )
        self.assertEqual(
            fitted.intercept,
            expected_intercept,
        )


if __name__ == "__main__":
    unittest.main()
