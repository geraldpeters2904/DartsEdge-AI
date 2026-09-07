import unittest

from app.services.simulation_service import simulate_match


class SimulationServiceTests(unittest.TestCase):

    def test_best_of_7_is_deterministic_from_leg_probability(self):
        profile_a = {"elo": 1500}
        profile_b = {"elo": 1500}

        first = simulate_match(
            profile_a,
            profile_b,
            leg_win_prob_a=0.5,
            best_of=7,
        )
        second = simulate_match(
            profile_a,
            profile_b,
            leg_win_prob_a=0.5,
            best_of=7,
        )

        self.assertEqual(first, second)

        self.assertEqual(first["player_a_win"], 0.5)
        self.assertEqual(first["player_b_win"], 0.5)

        self.assertEqual(
            first["scores"],
            {
                "4-0": 0.062,
                "4-1": 0.125,
                "4-2": 0.156,
                "4-3": 0.156,
                "0-4": 0.062,
                "1-4": 0.125,
                "2-4": 0.156,
                "3-4": 0.156,
            },
        )

        self.assertEqual(first["handicaps"]["player_a_minus_1_5"], 0.344)
        self.assertEqual(first["handicaps"]["player_a_minus_2_5"], 0.188)
        self.assertEqual(first["handicaps"]["player_b_plus_2_5"], 0.812)

        self.assertEqual(first["total_legs"]["over_5_5"], 0.625)
        self.assertEqual(first["total_legs"]["over_6_5"], 0.312)

    def test_pipeline_style_leg_probability_changes_match_result(self):
        profile_a = {"elo": 1500}
        profile_b = {"elo": 1500}

        result = simulate_match(
            profile_a,
            profile_b,
            leg_win_prob_a=0.65,
            best_of=7,
        )

        self.assertGreater(result["player_a_win"], 0.65)
        self.assertLess(result["player_b_win"], 0.35)


if __name__ == "__main__":
    unittest.main()
