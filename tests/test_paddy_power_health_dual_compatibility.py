import unittest
from unittest.mock import patch

from app.services.paddy_power_live_bridge import (
    PaddyPowerBridgeResolution,
)
from app.services.paddy_power_live_health_service import (
    check_paddy_power_live_health,
)


class PaddyPowerHealthDualCompatibilityTests(
    unittest.TestCase
):
    @patch(
        "app.services.paddy_power_live_health_service.resolve_capture_callable"
    )
    def test_old_resolver_patch_point(
        self,
        resolver,
    ):
        resolver.return_value = (
            PaddyPowerBridgeResolution(
                module_name="test.module",
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
        "app.services.paddy_power_live_health_service.build_paddy_power_capture_once"
    )
    def test_new_builder_patch_point(
        self,
        builder,
    ):
        class Service:
            def close(self):
                pass

        builder.return_value = (
            lambda db: None,
            Service(),
        )

        health = (
            check_paddy_power_live_health()
        )

        self.assertTrue(
            health.ready
        )

        self.assertEqual(
            health.function_name,
            "build_paddy_power_capture_once",
        )


if __name__ == "__main__":
    unittest.main()
