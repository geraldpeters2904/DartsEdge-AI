import unittest

from app.services.leg_market_calibration_service import (
    HANDICAP_CALIBRATION,
    TOTAL_LEGS_CALIBRATION,
    PlattCalibration,
    calibrate_handicap_probability,
    calibrate_total_legs_probability,
)


class PlattCalibrationTests(unittest.TestCase):

    def test_calibrates_probability_with_logit_transform(self):
        calibration = PlattCalibration(
            slope=0.225,
            intercept=-0.45,
        )

        calibrated = calibration.apply(0.95)

        self.assertGreater(calibrated, 0.0)
        self.assertLess(calibrated, 1.0)
        self.assertLess(calibrated, 0.95)
        self.assertAlmostEqual(
            calibrated,
            0.5529256841555502,
            places=6,
        )

    def test_handles_probability_boundaries(self):
        calibration = PlattCalibration(
            slope=0.225,
            intercept=-0.45,
        )

        low = calibration.apply(0.0)
        high = calibration.apply(1.0)

        self.assertGreater(low, 0.0)
        self.assertLess(high, 1.0)

    def test_rejects_probability_outside_unit_interval(self):
        calibration = PlattCalibration(
            slope=0.225,
            intercept=-0.45,
        )

        with self.assertRaises(ValueError):
            calibration.apply(-0.01)

        with self.assertRaises(ValueError):
            calibration.apply(1.01)


class LegMarketCalibrationTests(unittest.TestCase):

    def test_uses_validated_handicap_parameters(self):
        self.assertEqual(
            HANDICAP_CALIBRATION.slope,
            0.225,
        )
        self.assertEqual(
            HANDICAP_CALIBRATION.intercept,
            -0.45,
        )

    def test_uses_validated_total_legs_parameters(self):
        self.assertEqual(
            TOTAL_LEGS_CALIBRATION.slope,
            0.15,
        )
        self.assertEqual(
            TOTAL_LEGS_CALIBRATION.intercept,
            0.375,
        )

    def test_handicap_helper_compresses_extreme_probability(self):
        calibrated = calibrate_handicap_probability(
            0.9464
        )

        self.assertLess(calibrated, 0.9464)
        self.assertGreater(calibrated, 0.50)

    def test_total_legs_helper_lifts_low_probability(self):
        calibrated = calibrate_total_legs_probability(
            0.0632
        )

        self.assertGreater(calibrated, 0.0632)
        self.assertLess(calibrated, 0.50)


class CalibrationScopeTests(unittest.TestCase):
    def test_value_board_only_calibrates_validated_handicap_line(self):
        from pathlib import Path

        source = Path(
            "app/services/value_board_service.py"
        ).read_text()

        self.assertIn(
            'player_side == "a"\n'
            '            and line == -1.5',
            source,
        )
        self.assertIn(
            'player_side == "b"\n'
            '            and line == 1.5',
            source,
        )

    def test_value_board_only_calibrates_validated_total_legs_line(self):
        from pathlib import Path

        source = Path(
            "app/services/value_board_service.py"
        ).read_text()

        self.assertIn(
            "if line == 5.5:",
            source,
        )


if __name__ == "__main__":
    unittest.main()
