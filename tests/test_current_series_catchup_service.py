import unittest

from app.services.current_series_modus_fetcher import CURRENT_GROUPS


class CurrentSeriesCatchupTests(unittest.TestCase):
    def test_standard_week_groups_are_complete(self):
        self.assertEqual(
            CURRENT_GROUPS,
            (
                "Group A",
                "Group B",
                "Group C",
                "Final",
            ),
        )


if __name__ == "__main__":
    unittest.main()
