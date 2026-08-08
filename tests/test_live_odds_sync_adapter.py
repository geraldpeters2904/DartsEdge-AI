import unittest

from app.services.live_odds_sync_adapter import (
    build_live_odds_collector,
)


class LiveOddsSyncAdapterTests(
    unittest.TestCase
):
    def test_default_collector_has_primary_sources(
        self,
    ):
        collector = (
            build_live_odds_collector()
        )

        self.assertEqual(
            tuple(
                sorted(
                    collector.fetchers.keys()
                )
            ),
            (
                "bet365",
                "paddypower",
            ),
        )


if __name__ == "__main__":
    unittest.main()
