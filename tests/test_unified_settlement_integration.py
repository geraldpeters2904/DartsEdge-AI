import unittest

from app.services.unified_sync_manager_service import (
    UnifiedSynchronisationManager,
)


class UnifiedSettlementIntegrationTests(
    unittest.TestCase
):
    def test_settlement_runs_after_current_series(self):
        calls = []

        manager = (
            UnifiedSynchronisationManager(
                current_series_sync=(
                    lambda: (
                        calls.append(
                            "current"
                        )
                    )
                ),
                settlement_sync=(
                    lambda: (
                        calls.append(
                            "settlement"
                        )
                    )
                ),
                bookmaker_capture=(
                    lambda: (
                        calls.append(
                            "bookmaker"
                        )
                    )
                ),
                sleeper=(
                    lambda seconds: None
                ),
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


if __name__ == "__main__":
    unittest.main()
