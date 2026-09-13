import unittest

from datetime import datetime
from unittest.mock import MagicMock, patch

from app.services.bookmaker_capture_types import (
    BookmakerCaptureReport,
)
from app.services.live_unified_sync_builder import (
    build_live_unified_manager,
)


class CurrentSeriesLiveSyncWiringTests(unittest.TestCase):
    def test_manager_builds_with_default_bookmaker_capture(self):
        manager = build_live_unified_manager(
            poll_seconds=1,
        )

        self.assertIsNotNone(
            manager.bookmaker_capture
        )

    def test_default_capture_combines_category_and_events(
        self,
    ):
        category_report = BookmakerCaptureReport(
            bookmaker="Paddy Power",
            source_url="category",
            captured_at=datetime(
                2026, 9, 10, 10, 0
            ),
            extracted_prices=20,
            stored_prices=10,
            unchanged_prices=10,
            skipped_prices=0,
            challenge_detected=False,
            message="category",
        )

        event_report = BookmakerCaptureReport(
            bookmaker="Paddy Power",
            source_url="events",
            captured_at=datetime(
                2026, 9, 10, 10, 1
            ),
            extracted_prices=12,
            stored_prices=8,
            unchanged_prices=3,
            skipped_prices=1,
            challenge_detected=False,
            message="events",
        )

        capture_once = MagicMock(
            return_value=category_report
        )
        capture_service = MagicMock()
        fake_db = MagicMock()

        with patch(
            "app.services.live_unified_sync_builder."
            "build_paddy_power_capture_once",
            return_value=(
                capture_once,
                capture_service,
            ),
        ):
            with patch(
                "app.services.live_unified_sync_builder."
                "capture_paddy_power_discovered_events_report_once",
                return_value=event_report,
            ) as event_capture:
                with patch(
                    "app.db.SessionLocal",
                    return_value=fake_db,
                ):
                    manager = (
                        build_live_unified_manager(
                            poll_seconds=1,
                        )
                    )

                    report = (
                        manager.bookmaker_capture()
                    )

        capture_once.assert_called_once_with(
            fake_db
        )
        event_capture.assert_called_once_with(
            fake_db,
            category_html=(
                capture_service.browser_session.html()
            ),
            service=capture_service,
        )
        fake_db.close.assert_called_once()

        self.assertEqual(
            report.extracted_prices,
            32,
        )
        self.assertEqual(
            report.stored_prices,
            18,
        )
        self.assertEqual(
            report.unchanged_prices,
            13,
        )
        self.assertEqual(
            report.skipped_prices,
            1,
        )
        self.assertFalse(
            report.challenge_detected
        )
        self.assertEqual(
            report.captured_at,
            event_report.captured_at,
        )
        self.assertIn(
            "category and event",
            report.message,
        )

    def test_default_capture_treats_unpublished_modus_as_waiting(
        self,
    ):
        capture_once = MagicMock(
            side_effect=TimeoutError(
                "Timed out waiting for Paddy Power page content."
            )
        )
        capture_service = MagicMock()
        fake_db = MagicMock()

        with patch(
            "app.services.live_unified_sync_builder."
            "build_paddy_power_capture_once",
            return_value=(
                capture_once,
                capture_service,
            ),
        ):
            with patch(
                "app.db.SessionLocal",
                return_value=fake_db,
            ):
                manager = build_live_unified_manager(
                    poll_seconds=1,
                )

                report = manager.bookmaker_capture()

        self.assertEqual(report.extracted_prices, 0)
        self.assertEqual(report.stored_prices, 0)
        self.assertEqual(report.unchanged_prices, 0)
        self.assertEqual(report.skipped_prices, 0)
        self.assertFalse(report.challenge_detected)
        self.assertIn(
            "not currently published",
            report.message.lower(),
        )

        fake_db.close.assert_called_once()
        capture_service.close.assert_called_once()


    def test_default_capture_treats_unpublished_modus_as_waiting(
        self,
    ):
        capture_once = MagicMock(
            side_effect=TimeoutError(
                "Timed out waiting for Paddy Power page content."
            )
        )
        capture_service = MagicMock()
        fake_db = MagicMock()

        with patch(
            "app.services.live_unified_sync_builder."
            "build_paddy_power_capture_once",
            return_value=(
                capture_once,
                capture_service,
            ),
        ):
            with patch(
                "app.db.SessionLocal",
                return_value=fake_db,
            ):
                manager = build_live_unified_manager(
                    poll_seconds=1,
                )

                report = manager.bookmaker_capture()

        self.assertEqual(report.extracted_prices, 0)
        self.assertEqual(report.stored_prices, 0)
        self.assertEqual(report.unchanged_prices, 0)
        self.assertEqual(report.skipped_prices, 0)
        self.assertFalse(report.challenge_detected)
        self.assertIn(
            "not currently published",
            report.message.lower(),
        )

        fake_db.close.assert_called_once()
        capture_service.close.assert_called_once()


    def test_manager_builds_with_current_series_sync(self):
        manager = build_live_unified_manager(poll_seconds=1)
        self.assertIsNotNone(manager)



    def test_explicit_bookmaker_capture_overrides_default(self):
        callback = lambda: "custom"

        manager = build_live_unified_manager(
            bookmaker_capture=callback,
            poll_seconds=1,
        )

        self.assertIs(
            manager.bookmaker_capture,
            callback,
        )


if __name__ == "__main__":
    unittest.main()
