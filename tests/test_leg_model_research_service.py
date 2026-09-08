import unittest

from app.services.leg_market_validation_engine import (
    LegMarketValidationRecord,
)
from app.services.leg_model_research_service import (
    candidate_leg_win_probability,
)


class CandidateLegWinProbabilityTests(unittest.TestCase):

    def test_equal_profiles_produce_even_probability(self):
        probability = candidate_leg_win_probability(
            average_a=90.0,
            checkout_a=40.0,
            average_b=90.0,
            checkout_b=40.0,
            average_weight=0.7,
            checkout_weight=0.3,
            logistic_scale=8.0,
        )

        self.assertAlmostEqual(probability, 0.5, places=12)

    def test_production_parameters_match_production_leg_model(self):
        from types import SimpleNamespace

        from app.services.match_engine import leg_win_probability

        profile_a = SimpleNamespace(
            average=94.3,
            checkout=41.7,
        )
        profile_b = SimpleNamespace(
            average=88.6,
            checkout=37.2,
        )

        production = leg_win_probability(
            profile_a,
            profile_b,
        )
        candidate = candidate_leg_win_probability(
            average_a=profile_a.average,
            checkout_a=profile_a.checkout,
            average_b=profile_b.average,
            checkout_b=profile_b.checkout,
            average_weight=0.9,
            checkout_weight=0.1,
            logistic_scale=14.0,
        )

        self.assertAlmostEqual(
            candidate,
            production,
            places=12,
        )

    def test_candidate_parameters_change_probability(self):
        baseline = candidate_leg_win_probability(
            average_a=95.0,
            checkout_a=40.0,
            average_b=90.0,
            checkout_b=40.0,
            average_weight=0.7,
            checkout_weight=0.3,
            logistic_scale=8.0,
        )
        alternative = candidate_leg_win_probability(
            average_a=95.0,
            checkout_a=40.0,
            average_b=90.0,
            checkout_b=40.0,
            average_weight=1.0,
            checkout_weight=0.0,
            logistic_scale=6.0,
        )

        self.assertNotAlmostEqual(
            baseline,
            alternative,
            places=6,
        )


class CandidateDateDisjointWalkForwardTests(unittest.TestCase):

    def test_evaluates_candidate_with_date_disjoint_folds(self):
        from datetime import date, timedelta

        from app.services.leg_market_validation_engine import (
            LegMarketValidationRecord,
        )
        from app.services.leg_model_research_service import (
            evaluate_candidate_date_disjoint_walk_forward,
        )

        start = date(2026, 1, 1)

        records = tuple(
            LegMarketValidationRecord(
                match_id=index,
                player_a_leg_win_probability=0.5,
                player_a_handicap_probability=0.5,
                player_a_handicap_result=(
                    1 if index % 2 else 0
                ),
                total_legs_over_probability=0.5,
                total_legs_over_result=(
                    1 if index % 3 else 0
                ),
                player_a_average=90.0 + (index % 4),
                player_a_checkout=38.0 + (index % 3),
                player_b_average=89.0 + (index % 3),
                player_b_checkout=37.0 + (index % 2),
                best_of=7,
                match_date=(
                    start
                    + timedelta(days=(index - 1) // 2)
                ),
            )
            for index in range(1, 13)
        )

        report = evaluate_candidate_date_disjoint_walk_forward(
            records,
            average_weight=0.7,
            checkout_weight=0.3,
            logistic_scale=8.0,
            market="handicap",
            initial_train_size=6,
            test_size=2,
        )

        self.assertEqual(report.records, 12)
        self.assertGreaterEqual(report.folds_evaluated, 1)
        self.assertGreater(report.test_observations, 0)
        self.assertGreaterEqual(
            report.calibrated_brier_score,
            0.0,
        )
        self.assertLessEqual(
            report.calibrated_brier_score,
            1.0,
        )



class CandidateFixedHoldoutTests(unittest.TestCase):

    def test_evaluates_candidate_with_fixed_holdout(self):
        from datetime import date

        from app.services.leg_model_research_service import (
            evaluate_candidate_fixed_holdout,
        )

        train = tuple(
            LegMarketValidationRecord(
                match_id=index,
                match_date=date(2025, 1, index),
                best_of=7,
                player_a_average=90.0 + index,
                player_a_checkout=40.0,
                player_b_average=88.0,
                player_b_checkout=38.0,
                player_a_leg_win_probability=0.5,
                player_a_handicap_probability=0.5,
                player_a_handicap_result=index % 2,
                total_legs_over_probability=0.5,
                total_legs_over_result=(index + 1) % 2,
            )
            for index in range(1, 7)
        )

        test = tuple(
            LegMarketValidationRecord(
                match_id=100 + index,
                match_date=date(2025, 2, index),
                best_of=7,
                player_a_average=92.0 + index,
                player_a_checkout=41.0,
                player_b_average=87.0,
                player_b_checkout=37.0,
                player_a_leg_win_probability=0.5,
                player_a_handicap_probability=0.5,
                player_a_handicap_result=index % 2,
                total_legs_over_probability=0.5,
                total_legs_over_result=(index + 1) % 2,
            )
            for index in range(1, 4)
        )

        evaluation = evaluate_candidate_fixed_holdout(
            train,
            test,
            average_weight=0.9,
            checkout_weight=0.1,
            logistic_scale=14.0,
            market="handicap",
        )

        self.assertEqual(evaluation.train_size, 6)
        self.assertEqual(evaluation.test_size, 3)
        self.assertGreaterEqual(
            evaluation.raw_brier_score,
            0.0,
        )
        self.assertGreaterEqual(
            evaluation.calibrated_brier_score,
            0.0,
        )





class CandidateMarketProbabilityTests(unittest.TestCase):

    def test_builds_market_probabilities_from_retained_historical_features(self):
        from types import SimpleNamespace

        from app.services.leg_model_research_service import (
            candidate_market_probabilities,
        )

        record = SimpleNamespace(
            player_a_average=90.0,
            player_a_checkout=40.0,
            player_b_average=90.0,
            player_b_checkout=40.0,
            best_of=7,
        )

        result = candidate_market_probabilities(
            record,
            average_weight=0.7,
            checkout_weight=0.3,
            logistic_scale=8.0,
            handicap_line=-1.5,
            total_legs_line=5.5,
        )

        self.assertAlmostEqual(
            result["leg_win_probability"],
            0.5,
            places=12,
        )
        self.assertAlmostEqual(
            result["handicap_probability"],
            0.34375,
            places=12,
        )
        self.assertAlmostEqual(
            result["total_legs_over_probability"],
            0.625,
            places=12,
        )


class CandidateWalkForwardTests(unittest.TestCase):

    def test_evaluates_candidate_parameters_through_walk_forward(self):
        from app.services.leg_market_validation_engine import (
            LegMarketValidationRecord,
        )
        from app.services.leg_model_research_service import (
            evaluate_candidate_walk_forward,
        )

        records = tuple(
            LegMarketValidationRecord(
                match_id=index,
                player_a_leg_win_probability=0.5,
                player_a_handicap_probability=0.5,
                player_a_handicap_result=1 if index % 2 else 0,
                total_legs_over_probability=0.5,
                total_legs_over_result=1 if index % 3 else 0,
                player_a_average=90.0 + (index % 4),
                player_a_checkout=38.0 + (index % 3),
                player_b_average=89.0 + (index % 3),
                player_b_checkout=37.0 + (index % 2),
                best_of=7,
            )
            for index in range(1, 13)
        )

        report = evaluate_candidate_walk_forward(
            records,
            average_weight=0.7,
            checkout_weight=0.3,
            logistic_scale=8.0,
            market="handicap",
            initial_train_size=6,
            test_size=2,
        )

        self.assertEqual(report.records, 12)
        self.assertEqual(report.folds_evaluated, 3)
        self.assertEqual(report.test_observations, 6)
        self.assertGreaterEqual(report.raw_brier_score, 0.0)
        self.assertLessEqual(report.raw_brier_score, 1.0)
        self.assertGreaterEqual(
            report.calibrated_brier_score,
            0.0,
        )
        self.assertLessEqual(
            report.calibrated_brier_score,
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
