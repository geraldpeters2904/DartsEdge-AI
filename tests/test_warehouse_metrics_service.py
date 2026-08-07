import unittest
from pathlib import Path

from app.services.warehouse_metrics_service import WarehouseHealthMetrics


class WarehouseHealthMetricsTests(unittest.TestCase):
    def test_percentages_and_health(self):
        metrics = WarehouseHealthMetrics(
            root=Path("/tmp/imports"),
            discovered_series=10,
            complete_series=4,
            remaining_series=6,
            discovered_groups=20,
            ready_groups=1,
            incomplete_groups=2,
            imported_groups=17,
            partially_imported_groups=0,
            error_groups=0,
            expected_matches=100,
            validated_matches=95,
            missing_matches=5,
            imported_fixture_mappings=90,
            database_players=200,
            database_matches=1000,
            database_performances=1900,
            runner_status="running",
            runner_processed_matches=80,
            runner_remaining_matches=20,
            runner_total_matches=100,
            runner_current_series="Series 9",
            runner_current_week="Week 1",
            runner_current_group="Group A",
            runner_current_match_id=123,
            runner_last_message="Running.",
            runner_last_error=None,
        )

        self.assertEqual(metrics.series_completion_percentage, 40.0)
        self.assertEqual(metrics.validation_percentage, 95.0)
        self.assertEqual(metrics.runner_completion_percentage, 80.0)
        self.assertTrue(metrics.healthy)


if __name__ == "__main__":
    unittest.main()
