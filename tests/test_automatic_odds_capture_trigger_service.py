import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from app.services.automatic_odds_capture_trigger_service import (
    AutomaticOddsCaptureTrigger,
)


class Clock:
    def __init__(
        self,
        value: datetime,
    ) -> None:
        self.value = value

    def now(self):
        return self.value

    def advance(
        self,
        *,
        minutes: int,
    ) -> None:
        self.value = (
            self.value
            + timedelta(
                minutes=minutes
            )
        )


class AutomaticOddsCaptureTriggerTests(
    unittest.TestCase
):
    def setUp(self):
        self.clock = Clock(
            datetime(
                2026,
                8,
                13,
                9,
                0,
                0,
            )
        )
        self.trigger = (
            AutomaticOddsCaptureTrigger(
                zero_price_retry_seconds=1800.0,
                now_provider=self.clock.now,
            )
        )

    def test_zero_fixtures_does_not_capture(self):
        result = self.trigger.consider(
            future_fixtures=0
        )
        self.assertFalse(result.triggered)
        self.assertEqual(result.future_fixtures, 0)

    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "SessionLocal"
    )
    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "capture_paddy_power_discovered_events_report_once"
    )
    def test_new_fixture_count_triggers_capture(
        self,
        capture,
        session_local,
    ):
        db = SimpleNamespace(close=lambda: None)
        session_local.return_value = db
        capture.return_value = SimpleNamespace(
            extracted_prices=4,
            stored_prices=4,
            challenge_detected=False,
            message="completed",
        )

        result = self.trigger.consider(
            future_fixtures=2
        )

        self.assertTrue(result.triggered)
        self.assertTrue(result.ready)
        self.assertEqual(result.extracted_prices, 4)
        capture.assert_called_once_with(db)

    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "SessionLocal"
    )
    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "capture_paddy_power_discovered_events_report_once"
    )
    def test_unchanged_fixture_count_does_not_repeat_after_prices(
        self,
        capture,
        session_local,
    ):
        db = SimpleNamespace(close=lambda: None)
        session_local.return_value = db
        capture.return_value = SimpleNamespace(
            extracted_prices=2,
            stored_prices=2,
            challenge_detected=False,
            message="completed",
        )

        first = self.trigger.consider(
            future_fixtures=3
        )
        second = self.trigger.consider(
            future_fixtures=3
        )

        self.assertTrue(first.triggered)
        self.assertFalse(second.triggered)
        self.assertEqual(capture.call_count, 1)

    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "SessionLocal"
    )
    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "capture_paddy_power_discovered_events_report_once"
    )
    def test_zero_price_capture_enters_cooldown(
        self,
        capture,
        session_local,
    ):
        db = SimpleNamespace(close=lambda: None)
        session_local.return_value = db
        capture.return_value = SimpleNamespace(
            extracted_prices=0,
            stored_prices=0,
            challenge_detected=False,
            message="completed",
        )

        first = self.trigger.consider(
            future_fixtures=2
        )
        second = self.trigger.consider(
            future_fixtures=2
        )

        self.assertTrue(first.triggered)
        self.assertFalse(second.triggered)
        self.assertEqual(capture.call_count, 1)
        self.assertIn(
            "cooling down",
            second.message,
        )

    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "SessionLocal"
    )
    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "capture_paddy_power_discovered_events_report_once"
    )
    def test_zero_price_capture_retries_after_cooldown(
        self,
        capture,
        session_local,
    ):
        db = SimpleNamespace(close=lambda: None)
        session_local.return_value = db
        capture.return_value = SimpleNamespace(
            extracted_prices=0,
            stored_prices=0,
            challenge_detected=False,
            message="completed",
        )

        first = self.trigger.consider(
            future_fixtures=2
        )

        self.clock.advance(
            minutes=29,
        )
        blocked = self.trigger.consider(
            future_fixtures=2
        )

        self.clock.advance(
            minutes=1,
        )
        retry = self.trigger.consider(
            future_fixtures=2
        )

        self.assertTrue(first.triggered)
        self.assertFalse(blocked.triggered)
        self.assertTrue(retry.triggered)
        self.assertEqual(capture.call_count, 2)

    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "SessionLocal"
    )
    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "capture_paddy_power_discovered_events_report_once"
    )
    def test_fixture_count_change_bypasses_zero_price_cooldown(
        self,
        capture,
        session_local,
    ):
        db = SimpleNamespace(close=lambda: None)
        session_local.return_value = db
        capture.return_value = SimpleNamespace(
            extracted_prices=0,
            stored_prices=0,
            challenge_detected=False,
            message="completed",
        )

        first = self.trigger.consider(
            future_fixtures=2
        )
        changed = self.trigger.consider(
            future_fixtures=3
        )

        self.assertTrue(first.triggered)
        self.assertTrue(changed.triggered)
        self.assertEqual(capture.call_count, 2)

    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "SessionLocal"
    )
    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "capture_paddy_power_discovered_events_report_once"
    )
    def test_failed_capture_can_retry_next_cycle(
        self,
        capture,
        session_local,
    ):
        db = SimpleNamespace(close=lambda: None)
        session_local.return_value = db
        capture.side_effect = RuntimeError(
            "temporary error"
        )

        first = self.trigger.consider(
            future_fixtures=2
        )
        second = self.trigger.consider(
            future_fixtures=2
        )

        self.assertTrue(first.triggered)
        self.assertTrue(second.triggered)
        self.assertEqual(capture.call_count, 2)


    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "SessionLocal"
    )
    @patch(
        "app.services."
        "automatic_odds_capture_trigger_service."
        "capture_paddy_power_discovered_events_report_once"
    )
    def test_new_fixture_count_uses_discovered_event_capture(
        self,
        capture,
        session_local,
    ):
        db = SimpleNamespace(close=lambda: None)
        session_local.return_value = db
        capture.return_value = SimpleNamespace(
            extracted_prices=8,
            stored_prices=6,
            challenge_detected=False,
            message="completed",
        )

        result = self.trigger.consider(
            future_fixtures=2
        )

        self.assertTrue(result.triggered)
        self.assertTrue(result.ready)
        self.assertEqual(result.extracted_prices, 8)
        self.assertEqual(result.stored_prices, 6)
        capture.assert_called_once_with(db)


if __name__ == "__main__":
    unittest.main()
