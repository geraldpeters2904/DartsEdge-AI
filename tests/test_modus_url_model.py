import unittest

from app.providers.adapters.modus_official.urls import ModusUrlModel


class ModusUrlModelTests(unittest.TestCase):
    def setUp(self):
        self.urls = ModusUrlModel()

    def test_group_b_url(self):
        self.assertEqual(
            self.urls.results_url(
                series_id=15,
                week_id=178,
                group="Group B",
            ),
            (
                "https://modussuperseries.com/results?"
                "series_id=15&week_id=178&group=Group+B"
            ),
        )

    def test_plus_group_is_normalised(self):
        url = self.urls.results_url(
            series_id=15,
            week_id=178,
            group="Group+A",
        )
        self.assertTrue(url.endswith("group=Group+A"))

    def test_match_stats_url(self):
        self.assertEqual(
            self.urls.match_stats_url(18195),
            (
                "https://modussuperseries.com/"
                "match-db-stats.php?match_id=18195"
            ),
        )

    def test_invalid_group_is_rejected(self):
        with self.assertRaises(ValueError):
            self.urls.results_url(
                series_id=15,
                week_id=178,
                group="Unknown",
            )


if __name__ == "__main__":
    unittest.main()
