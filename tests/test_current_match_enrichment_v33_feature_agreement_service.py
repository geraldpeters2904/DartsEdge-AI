import unittest

from app.services.current_match_enrichment_v33_feature_agreement_service import (
    CurrentMatchEnrichmentV33FeatureAgreementService,
)


class CurrentMatchEnrichmentV33FeatureAgreementServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            CurrentMatchEnrichmentV33FeatureAgreementService()
        )

    def test_average(self):
        self.assertEqual(
            self.service._average(
                (1, 2, 3),
            ),
            2.0,
        )

    def test_average_empty_returns_none(self):
        self.assertIsNone(
            self.service._average(())
        )

    def test_percentage(self):
        self.assertEqual(
            self.service._percentage(
                3,
                4,
            ),
            75.0,
        )

    def test_percentage_zero_denominator_returns_none(self):
        self.assertIsNone(
            self.service._percentage(
                0,
                0,
            )
        )

    def test_build_low_agreement_band(self):
        selected = (
            {
                "correct": True,
                "agreement": 40.0,
            },
            {
                "correct": False,
                "agreement": 49.9,
            },
            {
                "correct": True,
                "agreement": 50.0,
            },
        )

        result = self.service._build_band(
            selected,
            lower=0.0,
            upper=50.0,
        )

        self.assertEqual(
            result.band,
            "0-50",
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

    def test_build_middle_agreement_band(self):
        selected = (
            {
                "correct": True,
                "agreement": 50.0,
            },
            {
                "correct": True,
                "agreement": 60.0,
            },
            {
                "correct": False,
                "agreement": 65.0,
            },
        )

        result = self.service._build_band(
            selected,
            lower=50.0,
            upper=65.0,
        )

        self.assertEqual(
            result.predictions,
            2,
        )

        self.assertEqual(
            result.correct,
            2,
        )

        self.assertEqual(
            result.accuracy,
            100.0,
        )

    def test_build_high_agreement_band_includes_100(self):
        selected = (
            {
                "correct": True,
                "agreement": 80.0,
            },
            {
                "correct": False,
                "agreement": 100.0,
            },
        )

        result = self.service._build_band(
            selected,
            lower=80.0,
            upper=101.0,
        )

        self.assertEqual(
            result.band,
            "80-100",
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

    def test_build_empty_band(self):
        result = self.service._build_band(
            (),
            lower=65.0,
            upper=80.0,
        )

        self.assertEqual(
            result.predictions,
            0,
        )

        self.assertEqual(
            result.correct,
            0,
        )

        self.assertIsNone(
            result.accuracy
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
