import unittest

from app.services.current_match_enrichment_v33_history_imbalance_service import (
    CurrentMatchEnrichmentV33HistoryImbalanceService,
)


class CurrentMatchEnrichmentV33HistoryImbalanceServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33HistoryImbalanceService()
        )

    def test_build_band_calculates_accuracy_and_support(self):
        selected = (
            {
                "history_gap": 0,
                "correct": True,
                "supports": True,
                "support_strength": 0.08,
            },
            {
                "history_gap": 1,
                "correct": False,
                "supports": True,
                "support_strength": 0.06,
            },
            {
                "history_gap": 2,
                "correct": True,
                "supports": False,
                "support_strength": None,
            },
        )

        result = self.service._build_band(
            selected,
            lower=0,
            upper=2,
        )

        self.assertEqual(
            result.band,
            "0-1",
        )

        self.assertEqual(
            result.predictions,
            2,
        )

        self.assertEqual(
            result.correct,
            1,
        )

        self.assertEqual(
            result.accuracy,
            50.0,
        )

        self.assertEqual(
            result.recent_win_rate_supporting,
            2,
        )

        self.assertEqual(
            result.recent_win_rate_supporting_correct,
            1,
        )

        self.assertEqual(
            result.recent_win_rate_support_rate,
            100.0,
        )

        self.assertEqual(
            result.recent_win_rate_support_accuracy,
            50.0,
        )

        self.assertEqual(
            result.average_recent_win_rate_support_strength,
            0.07,
        )

    def test_build_band_respects_gap_boundaries(self):
        selected = (
            {
                "history_gap": 1,
                "correct": True,
                "supports": True,
                "support_strength": 0.05,
            },
            {
                "history_gap": 2,
                "correct": True,
                "supports": True,
                "support_strength": 0.05,
            },
            {
                "history_gap": 4,
                "correct": True,
                "supports": True,
                "support_strength": 0.05,
            },
            {
                "history_gap": 5,
                "correct": True,
                "supports": True,
                "support_strength": 0.05,
            },
        )

        result = self.service._build_band(
            selected,
            lower=2,
            upper=5,
        )

        self.assertEqual(
            result.band,
            "2-4",
        )

        self.assertEqual(
            result.predictions,
            2,
        )

    def test_open_ended_band(self):
        selected = (
            {
                "history_gap": 9,
                "correct": True,
                "supports": True,
                "support_strength": 0.05,
            },
            {
                "history_gap": 10,
                "correct": False,
                "supports": True,
                "support_strength": 0.07,
            },
            {
                "history_gap": 15,
                "correct": True,
                "supports": False,
                "support_strength": None,
            },
        )

        result = self.service._build_band(
            selected,
            lower=10,
            upper=None,
        )

        self.assertEqual(
            result.band,
            "10+",
        )

        self.assertEqual(
            result.predictions,
            2,
        )

    def test_empty_band(self):
        result = self.service._build_band(
            (),
            lower=5,
            upper=10,
        )

        self.assertEqual(
            result.predictions,
            0,
        )

        self.assertIsNone(
            result.accuracy,
        )

        self.assertIsNone(
            result.recent_win_rate_support_rate,
        )

        self.assertIsNone(
            result.recent_win_rate_support_accuracy,
        )

        self.assertIsNone(
            result.average_recent_win_rate_support_strength,
        )

    def test_average(self):
        self.assertEqual(
            self.service._average(
                (0.02, 0.04, 0.06),
            ),
            0.04,
        )

        self.assertIsNone(
            self.service._average(
                ()
            )
        )

    def test_percentage(self):
        self.assertEqual(
            self.service._percentage(
                3,
                4,
            ),
            75.0,
        )

        self.assertIsNone(
            self.service._percentage(
                0,
                0,
            )
        )

    def test_requires_offsets(self):
        with self.assertRaisesRegex(
            ValueError,
            "at least one",
        ):
            self.service.analyse(
                object(),
                offsets=(),
            )

    def test_rejects_invalid_minimum_history_upper(self):
        with self.assertRaisesRegex(
            ValueError,
            "greater than zero",
        ):
            self.service.analyse(
                object(),
                offsets=(100,),
                minimum_history_upper=0,
            )


if __name__ == "__main__":
    unittest.main()
