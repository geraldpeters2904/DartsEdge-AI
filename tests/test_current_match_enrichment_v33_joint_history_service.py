import unittest

from app.services.current_match_enrichment_v33_joint_history_service import (
    CurrentMatchEnrichmentV33JointHistoryService,
)


class CurrentMatchEnrichmentV33JointHistoryServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33JointHistoryService()
        )

    def test_both_0_2_band(self):
        self.assertTrue(
            self.service._in_band(
                1,
                2,
                "both_0_2",
            )
        )

        self.assertFalse(
            self.service._in_band(
                1,
                3,
                "both_0_2",
            )
        )

    def test_one_0_2_other_3_9_band(self):
        self.assertTrue(
            self.service._in_band(
                2,
                7,
                "one_0_2_other_3_9",
            )
        )

        self.assertTrue(
            self.service._in_band(
                5,
                1,
                "one_0_2_other_3_9",
            )
        )

        self.assertFalse(
            self.service._in_band(
                2,
                10,
                "one_0_2_other_3_9",
            )
        )

    def test_one_0_2_other_10_plus_band(self):
        self.assertTrue(
            self.service._in_band(
                1,
                10,
                "one_0_2_other_10_plus",
            )
        )

        self.assertTrue(
            self.service._in_band(
                20,
                2,
                "one_0_2_other_10_plus",
            )
        )

        self.assertFalse(
            self.service._in_band(
                2,
                9,
                "one_0_2_other_10_plus",
            )
        )

    def test_both_3_plus_band(self):
        self.assertTrue(
            self.service._in_band(
                3,
                3,
                "both_3_plus",
            )
        )

        self.assertTrue(
            self.service._in_band(
                7,
                20,
                "both_3_plus",
            )
        )

        self.assertFalse(
            self.service._in_band(
                2,
                20,
                "both_3_plus",
            )
        )

    def test_unknown_band_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unknown joint history band",
        ):
            self.service._in_band(
                1,
                2,
                "unknown",
            )

    def test_build_band_calculates_support_metrics(self):
        selected = (
            {
                "history_a": 1,
                "history_b": 2,
                "correct": True,
                "supports": True,
                "support_strength": 0.08,
            },
            {
                "history_a": 0,
                "history_b": 2,
                "correct": False,
                "supports": True,
                "support_strength": 0.06,
            },
            {
                "history_a": 1,
                "history_b": 8,
                "correct": True,
                "supports": False,
                "support_strength": None,
            },
        )

        result = self.service._build_band(
            selected,
            band="both_0_2",
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

    def test_empty_band(self):
        result = self.service._build_band(
            (),
            band="both_0_2",
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

    def test_requires_offsets(self):
        with self.assertRaisesRegex(
            ValueError,
            "at least one",
        ):
            self.service.analyse(
                object(),
                offsets=(),
            )


if __name__ == "__main__":
    unittest.main()
