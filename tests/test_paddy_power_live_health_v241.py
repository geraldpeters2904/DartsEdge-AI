import unittest
from unittest.mock import patch

from app.services.paddy_power_live_health_service import (
    check_paddy_power_live_health,
)


class PaddyPowerLiveHealthV241Tests(
    unittest.TestCase
):
    @patch(
        "app.services.paddy_power_live_health_service.build_paddy_power_capture_once"
    )
    def test_health_ready_for_real_builder(
        self,
        builder,
    ):
        class Service:
            closed = False

            def close(self):
                self.closed = True

        service = Service()

        builder.return_value = (
            lambda db: None,
            service,
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

        self.assertTrue(
            service.closed
        )


if __name__ == "__main__":
    unittest.main()
