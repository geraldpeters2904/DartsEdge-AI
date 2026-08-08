import unittest
from unittest.mock import patch

from app.services.paddy_power_live_bridge import (
    PaddyPowerBridgeResolution,
)
from app.services.paddy_power_live_health_service import (
    check_paddy_power_live_health,
)


class PaddyPowerLiveHealthTests(
    unittest.TestCase
):
    @patch(
        "app.services.paddy_power_live_health_service.resolve_capture_callable"
    )
    def test_ready_when_callable_resolves(
        self,
        resolve,
    ):
        resolve.return_value = (
            PaddyPowerBridgeResolution(
                module_name="app.services.fake",
                function_name="capture",
                callable=lambda: [],
            )
        )

        health = (
            check_paddy_power_live_health()
        )

        self.assertTrue(
            health.ready
        )
        self.assertEqual(
            health.function_name,
            "capture",
        )

    @patch(
        "app.services.paddy_power_live_health_service.resolve_capture_callable"
    )
    def test_not_ready_when_resolution_fails(
        self,
        resolve,
    ):
        resolve.side_effect = (
            RuntimeError(
                "not available"
            )
        )

        health = (
            check_paddy_power_live_health()
        )

        self.assertFalse(
            health.ready
        )
        self.assertIn(
            "not available",
            health.error,
        )


if __name__ == "__main__":
    unittest.main()
