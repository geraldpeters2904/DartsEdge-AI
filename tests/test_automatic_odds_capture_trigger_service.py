import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.automatic_odds_capture_trigger_service import (
    AutomaticOddsCaptureTrigger,
)


class AutomaticOddsCaptureTriggerTests(
    unittest.TestCase
):
    def setUp(self):
        self.trigger = (
            AutomaticOddsCaptureTrigger()
        )

    def test_zero_fixtures_does_not_capture(self):
        result = self.trigger.consider(
            future_fixtures=0
        )

        self.assertFalse(
            result.triggered
        )

        self.assertEqual(
            result.future_fixtures,
            0,
        )

    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "SessionLocal"
    )
    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "run_existing_paddy_power_capture"
    )
    def test_new_fixture_count_triggers_capture(
        self,
        capture,
        session_local,
    ):
        db = SimpleNamespace(
            close=lambda: None
        )

        session_local.return_value = db

        capture.return_value = SimpleNamespace(
            ready=True,
            report=SimpleNamespace(
                extracted_prices=4,
                stored_prices=4,
            ),
            message="completed",
            error=None,
        )

        result = self.trigger.consider(
            future_fixtures=2
        )

        self.assertTrue(
            result.triggered
        )

        self.assertTrue(
            result.ready
        )

        self.assertEqual(
            result.extracted_prices,
            4,
        )

        capture.assert_called_once_with(
            db
        )

    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "SessionLocal"
    )
    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "run_existing_paddy_power_capture"
    )
    def test_unchanged_fixture_count_does_not_repeat(
        self,
        capture,
        session_local,
    ):
        db = SimpleNamespace(
            close=lambda: None
        )

        session_local.return_value = db

        capture.return_value = SimpleNamespace(
            ready=True,
            report=SimpleNamespace(
                extracted_prices=2,
                stored_prices=2,
            ),
            message="completed",
            error=None,
        )

        first = self.trigger.consider(
            future_fixtures=3
        )

        second = self.trigger.consider(
            future_fixtures=3
        )

        self.assertTrue(
            first.triggered
        )

        self.assertFalse(
            second.triggered
        )

        self.assertEqual(
            capture.call_count,
            1,
        )

    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "SessionLocal"
    )
    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "run_existing_paddy_power_capture"
    )
    def test_zero_price_capture_retries_next_cycle(
        self,
        capture,
        session_local,
    ):
        db = SimpleNamespace(
            close=lambda: None
        )

        session_local.return_value = db

        capture.return_value = SimpleNamespace(
            ready=True,
            report=SimpleNamespace(
                extracted_prices=0,
                stored_prices=0,
            ),
            message="completed",
            error=None,
        )

        first = self.trigger.consider(
            future_fixtures=2
        )

        second = self.trigger.consider(
            future_fixtures=2
        )

        self.assertTrue(
            first.triggered
        )

        self.assertTrue(
            second.triggered
        )

        self.assertEqual(
            capture.call_count,
            2,
        )

        self.assertEqual(
            first.extracted_prices,
            0,
        )

        self.assertIn(
            "retried",
            first.message,
        )


    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "SessionLocal"
    )
    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "run_existing_paddy_power_capture"
    )
    def test_failed_capture_can_retry_next_cycle(
        self,
        capture,
        session_local,
    ):
        db = SimpleNamespace(
            close=lambda: None
        )

        session_local.return_value = db

        capture.return_value = SimpleNamespace(
            ready=False,
            report=None,
            message="capture failed",
            error="temporary error",
        )

        first = self.trigger.consider(
            future_fixtures=2
        )

        second = self.trigger.consider(
            future_fixtures=2
        )

        self.assertTrue(
            first.triggered
        )

        self.assertTrue(
            second.triggered
        )

        self.assertEqual(
            capture.call_count,
            2,
        )


if __name__ == "__main__":
    unittest.main()
