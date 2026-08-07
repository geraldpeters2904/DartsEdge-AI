import unittest
from datetime import datetime
from types import SimpleNamespace

from app.services.bookmaker_capture_manager_service import (
    BookmakerCaptureManager,
)


class FakeDb:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class CaptureManagerTests(
    unittest.TestCase
):
    def report(
        self,
        *,
        challenge=False,
        stored=1,
        unchanged=0,
    ):
        return SimpleNamespace(
            bookmaker="Paddy Power",
            source_url="https://example.test",
            captured_at=(
                datetime.utcnow()
            ),
            extracted_prices=(
                stored
                + unchanged
            ),
            stored_prices=stored,
            unchanged_prices=(
                unchanged
            ),
            skipped_prices=0,
            challenge_detected=(
                challenge
            ),
            message=(
                "challenge"
                if challenge
                else "ok"
            ),
        )

    def test_counts_successful_cycle(self):
        manager = (
            BookmakerCaptureManager(
                capture_once=(
                    lambda db: self.report(
                        stored=2
                    )
                ),
                sleeper=lambda seconds: None,
            )
        )

        db = FakeDb()

        result = manager.run_cycle(
            db
        )

        self.assertEqual(
            result.stored_prices,
            2,
        )

        status = manager.status()

        self.assertEqual(
            status.cycles,
            1,
        )

        self.assertEqual(
            status.successful_cycles,
            1,
        )

        self.assertEqual(
            status.total_stored_prices,
            2,
        )

    def test_stops_on_challenge(self):
        manager = (
            BookmakerCaptureManager(
                capture_once=(
                    lambda db: self.report(
                        challenge=True,
                        stored=0,
                    )
                ),
                poll_seconds=1,
                sleeper=lambda seconds: None,
            )
        )

        status = (
            manager.run_forever(
                session_factory=(
                    FakeDb
                ),
                max_cycles=10,
            )
        )

        self.assertFalse(
            status.running
        )

        self.assertEqual(
            status.cycles,
            1,
        )

        self.assertEqual(
            status.challenge_cycles,
            1,
        )

    def test_stops_after_failure_limit(self):
        calls = {
            "count": 0,
        }

        def fail(
            db,
        ):
            calls[
                "count"
            ] += 1
            raise RuntimeError(
                "temporary failure"
            )

        manager = (
            BookmakerCaptureManager(
                capture_once=fail,
                poll_seconds=1,
                retry_seconds=1,
                max_consecutive_failures=3,
                sleeper=lambda seconds: None,
            )
        )

        status = (
            manager.run_forever(
                session_factory=(
                    FakeDb
                ),
                max_cycles=10,
            )
        )

        self.assertEqual(
            calls["count"],
            3,
        )

        self.assertEqual(
            status.failed_cycles,
            3,
        )

        self.assertIn(
            "too many consecutive failures",
            status.last_message,
        )

    def test_max_cycles_stops_cleanly(self):
        manager = (
            BookmakerCaptureManager(
                capture_once=(
                    lambda db: self.report()
                ),
                poll_seconds=1,
                sleeper=lambda seconds: None,
            )
        )

        status = (
            manager.run_forever(
                session_factory=(
                    FakeDb
                ),
                max_cycles=3,
            )
        )

        self.assertEqual(
            status.cycles,
            3,
        )

        self.assertEqual(
            status.successful_cycles,
            3,
        )


if __name__ == "__main__":
    unittest.main()
