import unittest

from app.services.current_match_enrichment_v33_dual_low_history_consensus_risk_service import (
    CurrentMatchEnrichmentV33DualLowHistoryConsensusRiskService,
)


class CurrentMatchEnrichmentV33DualLowHistoryConsensusRiskServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33DualLowHistoryConsensusRiskService()
        )

    def test_below_80_band(self):
        self.assertTrue(
            self.service._in_band(
                66.667,
                "below_80",
            )
        )

        self.assertFalse(
            self.service._in_band(
                80.0,
                "below_80",
            )
        )

    def test_80_to_below_100_band(self):
        self.assertTrue(
            self.service._in_band(
                80.0,
                "80_to_below_100",
            )
        )

        self.assertTrue(
            self.service._in_band(
                99.999,
                "80_to_below_100",
            )
        )

        self.assertFalse(
            self.service._in_band(
                100.0,
                "80_to_below_100",
            )
        )

    def test_exactly_100_band(self):
        self.assertTrue(
            self.service._in_band(
                100.0,
                "exactly_100",
            )
        )

        self.assertFalse(
            self.service._in_band(
                99.999,
                "exactly_100",
            )
        )

    def test_none_agreement_matches_no_band(self):
        self.assertFalse(
            self.service._in_band(
                None,
                "below_80",
            )
        )

    def test_unknown_band_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unknown agreement band",
        ):
            self.service._in_band(
                80.0,
                "unknown",
            )

    def test_build_band_calculates_metrics(self):
        selected = (
            {
                "agreement": 100.0,
                "correct": True,
                "favourite_probability": 68.0,
                "confidence": 40.0,
            },
            {
                "agreement": 100.0,
                "correct": False,
                "favourite_probability": 70.0,
                "confidence": 44.0,
            },
            {
                "agreement": 80.0,
                "correct": True,
                "favourite_probability": 66.0,
                "confidence": 38.0,
            },
        )

        result = self.service._build_band(
            selected,
            band="exactly_100",
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
            result.average_favourite_probability,
            69.0,
        )

        self.assertEqual(
            result.average_confidence,
            42.0,
        )

    def test_empty_band(self):
        result = self.service._build_band(
            (),
            band="exactly_100",
        )

        self.assertEqual(
            result.predictions,
            0,
        )

        self.assertIsNone(
            result.accuracy,
        )

        self.assertIsNone(
            result.average_favourite_probability,
        )

        self.assertIsNone(
            result.average_confidence,
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

    def test_rejects_invalid_history_threshold(self):
        with self.assertRaisesRegex(
            ValueError,
            "greater than zero",
        ):
            self.service.analyse(
                object(),
                offsets=(100,),
                history_threshold=0,
            )


if __name__ == "__main__":
    unittest.main()
