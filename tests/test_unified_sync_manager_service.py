import unittest

from app.services.unified_sync_manager_service import (
    UnifiedSynchronisationManager,
)


class UnifiedSyncManagerTests(
    unittest.TestCase
):
    def test_runs_live_jobs_each_cycle(self):
        calls = []

        manager = (
            UnifiedSynchronisationManager(
                current_series_sync=(
                    lambda: calls.append(
                        "current"
                    )
                    or "current ok"
                ),
                settlement_sync=(
                    lambda: calls.append(
                        "settlement"
                    )
                    or "settlement ok"
                ),
                bookmaker_capture=(
                    lambda: calls.append(
                        "bookmaker"
                    )
                    or "bookmaker ok"
                ),
                historical_backfill=(
                    lambda: calls.append(
                        "historical"
                    )
                    or "historical ok"
                ),
                historical_every_n_cycles=5,
                sleeper=lambda seconds: None,
            )
        )

        manager.run_cycle()

        self.assertEqual(
            calls,
            [
                "current",
                "settlement",
                "bookmaker",
            ],
        )

    def test_historical_runs_at_lower_frequency(self):
        calls = []

        manager = (
            UnifiedSynchronisationManager(
                current_series_sync=(
                    lambda: None
                ),
                historical_backfill=(
                    lambda: calls.append(
                        "historical"
                    )
                ),
                historical_every_n_cycles=3,
                sleeper=lambda seconds: None,
            )
        )

        manager.run_cycle()
        manager.run_cycle()
        manager.run_cycle()

        self.assertEqual(
            calls,
            [
                "historical",
            ],
        )

    def test_failure_isolated_to_job(self):
        calls = []

        def fail():
            calls.append(
                "failed"
            )
            raise RuntimeError(
                "boom"
            )

        manager = (
            UnifiedSynchronisationManager(
                current_series_sync=fail,
                settlement_sync=(
                    lambda: calls.append(
                        "settlement"
                    )
                ),
                bookmaker_capture=(
                    lambda: calls.append(
                        "bookmaker"
                    )
                ),
                sleeper=lambda seconds: None,
            )
        )

        status = (
            manager.run_cycle()
        )

        self.assertEqual(
            calls,
            [
                "failed",
                "settlement",
                "bookmaker",
            ],
        )

        self.assertEqual(
            status.failed_cycles,
            1,
        )

        self.assertIn(
            "boom",
            status.last_error,
        )

    def test_max_cycles_stops_cleanly(self):
        calls = []

        manager = (
            UnifiedSynchronisationManager(
                current_series_sync=(
                    lambda: calls.append(
                        "current"
                    )
                ),
                poll_seconds=1,
                sleeper=lambda seconds: None,
            )
        )

        status = (
            manager.run_forever(
                max_cycles=3
            )
        )

        self.assertFalse(
            status.running
        )

        self.assertEqual(
            status.cycles,
            3,
        )

        self.assertEqual(
            len(
                calls
            ),
            3,
        )


if __name__ == "__main__":
    unittest.main()
