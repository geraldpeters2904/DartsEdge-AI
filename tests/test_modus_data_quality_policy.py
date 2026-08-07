import unittest

from app.services.modus_data_quality_policy import (
    ModusDataQualityPolicy,
)


class ModusDataQualityPolicyTests(
    unittest.TestCase
):
    def setUp(self):
        self.policy = ModusDataQualityPolicy()

    def test_matching_percentage_is_preserved(self):
        result = (
            self.policy
            .resolve_checkout_percentage(
                completed=2,
                attempts=5,
                displayed_value="40%",
            )
        )

        self.assertEqual(
            result.percentage,
            40.0,
        )
        self.assertFalse(result.recovered)
        self.assertIsNone(
            result.recovery_reason
        )

    def test_conflicting_percentage_is_recovered(self):
        result = (
            self.policy
            .resolve_checkout_percentage(
                completed=4,
                attempts=9,
                displayed_value="36%",
            )
        )

        self.assertEqual(
            result.percentage,
            44.444,
        )
        self.assertTrue(result.recovered)
        self.assertEqual(
            result.recovery_reason,
            "conflicting_checkout_percentage",
        )

    def test_missing_percentage_is_recovered(self):
        result = (
            self.policy
            .resolve_checkout_percentage(
                completed=0,
                attempts=4,
                displayed_value="--%",
            )
        )

        self.assertEqual(
            result.percentage,
            0.0,
        )
        self.assertTrue(result.recovered)
        self.assertEqual(
            result.recovery_reason,
            "missing_checkout_percentage",
        )

    def test_nonzero_missing_percentage_is_derived(self):
        result = (
            self.policy
            .resolve_checkout_percentage(
                completed=2,
                attempts=5,
                displayed_value="--%",
            )
        )

        self.assertEqual(
            result.percentage,
            40.0,
        )

    def test_unrecognised_text_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "number between 0 and 100",
        ):
            self.policy.resolve_checkout_percentage(
                completed=2,
                attempts=5,
                displayed_value="unknown",
            )

    def test_percentage_above_one_hundred_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "between 0 and 100",
        ):
            self.policy.resolve_checkout_percentage(
                completed=2,
                attempts=5,
                displayed_value="101%",
            )


if __name__ == "__main__":
    unittest.main()
