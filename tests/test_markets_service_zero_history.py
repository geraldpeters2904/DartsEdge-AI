import unittest

from app.services.markets_service import one80_markets


class MarketsServiceZeroHistoryTests(unittest.TestCase):
    def test_two_zero_history_players_do_not_raise(self):
        markets = one80_markets(0.0, 0.0)

        self.assertEqual(markets["most_180s_a"], 0.5)
        self.assertEqual(markets["most_180s_b"], 0.5)
        self.assertFalse(markets["most_180s_data_available"])
        self.assertEqual(markets["player_a"]["over_0_5"], 0.0)
        self.assertEqual(markets["player_b"]["over_0_5"], 0.0)

    def test_normal_history_uses_three_way_poisson_split(self):

        markets = one80_markets(2.0, 1.0)

        self.assertEqual(markets["most_180s_a"], 0.606)

        self.assertEqual(markets["most_180s_draw"], 0.212)

        self.assertEqual(markets["most_180s_b"], 0.183)

        self.assertTrue(markets["most_180s_data_available"])

    def test_none_values_are_treated_as_missing_history(self):
        markets = one80_markets(None, None)

        self.assertEqual(markets["most_180s_a"], 0.5)
        self.assertFalse(markets["most_180s_data_available"])


    def test_builds_total_180s_from_combined_expectation(self):
        markets = one80_markets(2.0, 1.0)

        self.assertEqual(markets["total"]["expected"], 3.0)
        self.assertEqual(markets["total"]["over_0_5"], 0.95)
        self.assertEqual(markets["total"]["over_1_5"], 0.801)
        self.assertEqual(markets["total"]["over_2_5"], 0.577)
        self.assertEqual(markets["total"]["over_3_5"], 0.353)

    def test_most_180s_is_three_way_poisson_probability(self):
        markets = one80_markets(2.0, 1.0)

        self.assertEqual(markets["most_180s_a"], 0.606)
        self.assertEqual(markets["most_180s_draw"], 0.212)
        self.assertEqual(markets["most_180s_b"], 0.183)

        total_probability = (
            markets["most_180s_a"]
            + markets["most_180s_draw"]
            + markets["most_180s_b"]
        )
        self.assertAlmostEqual(total_probability, 1.001, places=3)



if __name__ == "__main__":
    unittest.main()
