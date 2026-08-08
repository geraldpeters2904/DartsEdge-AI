import unittest
from unittest.mock import patch

from app.services.paddy_power_live_bridge import (
    PaddyPowerBridgeResolution,
    resolve_capture_callable,
)


class PaddyPowerBridgeCompatibilityV242Tests(unittest.TestCase):
    @patch(
        "app.services.paddy_power_live_bridge.build_paddy_power_capture_once"
    )
    def test_real_builder_resolves(self, builder):
        class Service:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        service = Service()
        capture = lambda db: None

        builder.return_value = (
            capture,
            service,
        )

        resolution = resolve_capture_callable()

        self.assertIsInstance(
            resolution,
            PaddyPowerBridgeResolution,
        )
        self.assertEqual(
            resolution.function_name,
            "build_paddy_power_capture_once",
        )
        self.assertTrue(
            service.closed
        )


if __name__ == "__main__":
    unittest.main()
