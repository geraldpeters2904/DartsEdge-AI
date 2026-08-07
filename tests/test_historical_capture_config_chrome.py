import tempfile
import unittest
from pathlib import Path

from app.services.historical_capture_config import (
    HistoricalCaptureConfig,
    HistoricalCaptureConfigService,
)


class HistoricalCaptureConfigChromeTests(unittest.TestCase):
    def test_chrome_provider_is_valid(self):
        config = HistoricalCaptureConfig(
            provider="chrome",
            browser_timeout_seconds=30.0,
            delay_between_captures_seconds=3.0,
            retry_limit=3,
            retry_delay_seconds=5.0,
            stop_on_access_challenge=True,
        )

        config.validate()

    def test_chrome_provider_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            service = HistoricalCaptureConfigService()

            config = HistoricalCaptureConfig(
                provider="chrome",
                browser_timeout_seconds=30.0,
                delay_between_captures_seconds=3.0,
                retry_limit=3,
                retry_delay_seconds=5.0,
                stop_on_access_challenge=True,
            )

            service.save(root_path, config)
            loaded = service.load(root_path)

            self.assertEqual(loaded.provider, "chrome")


if __name__ == "__main__":
    unittest.main()
