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

    def test_normal_history_keeps_proportional_split(self):
        markets = one80_markets(2.0, 1.0)

        self.assertEqual(markets["most_180s_a"], 0.667)
        self.assertEqual(markets["most_180s_b"], 0.333)
        self.assertTrue(markets["most_180s_data_available"])

    def test_none_values_are_treated_as_missing_history(self):
        markets = one80_markets(None, None)

        self.assertEqual(markets["most_180s_a"], 0.5)
        self.assertFalse(markets["most_180s_data_available"])


if __name__ == "__main__":
    unittest.main()
