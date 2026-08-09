import unittest

from app.services.live_unified_sync_builder import build_live_unified_manager


class CurrentSeriesLiveSyncWiringTests(unittest.TestCase):
    def test_manager_builds_with_current_series_sync(self):
        manager = build_live_unified_manager(poll_seconds=1)
        self.assertIsNotNone(manager)


if __name__ == "__main__":
    unittest.main()
