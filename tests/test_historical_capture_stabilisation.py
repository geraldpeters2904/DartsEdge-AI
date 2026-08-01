import tempfile
import unittest
from pathlib import Path

from app.services.historical_capture_config import (
    CONFIG_FILENAME,
    HistoricalCaptureConfig,
    HistoricalCaptureConfigService,
)
from app.services.historical_workflow_event_log import (
    EVENT_LOG_FILENAME,
    HistoricalWorkflowEventLog,
)


class HistoricalCaptureConfigTests(unittest.TestCase):
    def setUp(self):
        self.service = HistoricalCaptureConfigService()

    def test_default_configuration_uses_manual_provider(self):
        with tempfile.TemporaryDirectory() as root:
            config = self.service.load(root)

        self.assertEqual(config.provider, "manual")
        self.assertEqual(config.retry_limit, 3)
        self.assertEqual(
            config.delay_between_captures_seconds,
            3.0,
        )

    def test_saves_and_loads_safari_configuration(self):
        with tempfile.TemporaryDirectory() as root:
            saved = self.service.save(
                root,
                HistoricalCaptureConfig(
                    provider="safari",
                    browser_timeout_seconds=40,
                    delay_between_captures_seconds=4,
                    retry_limit=2,
                    retry_delay_seconds=6,
                ),
            )

            loaded = self.service.load(root)

            self.assertTrue(
                Path(root, CONFIG_FILENAME).is_file()
            )

        self.assertEqual(saved.provider, "safari")
        self.assertEqual(loaded.provider, "safari")
        self.assertEqual(
            loaded.browser_timeout_seconds,
            40,
        )
        self.assertEqual(loaded.retry_limit, 2)

    def test_rejects_unknown_provider(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported capture provider",
        ):
            HistoricalCaptureConfig(
                provider="unknown",
            ).validate()

    def test_rejects_negative_retry_limit(self):
        with self.assertRaisesRegex(
            ValueError,
            "Retry limit",
        ):
            HistoricalCaptureConfig(
                retry_limit=-1,
            ).validate()


class HistoricalWorkflowEventLogTests(unittest.TestCase):
    def setUp(self):
        self.log = HistoricalWorkflowEventLog()

    def test_appends_and_reads_structured_event(self):
        with tempfile.TemporaryDirectory() as root:
            self.log.append(
                root,
                event_type="capture_started",
                message="Starting match 16956.",
                match_id=16956,
                series_id=14,
                week_id=165,
                group="Group A",
                provider="safari",
                attempt=1,
            )

            events = self.log.read(root)

            self.assertTrue(
                Path(
                    root,
                    EVENT_LOG_FILENAME,
                ).is_file()
            )

        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0].event_type,
            "CAPTURE_STARTED",
        )
        self.assertEqual(events[0].match_id, 16956)
        self.assertEqual(
            events[0].provider,
            "safari",
        )

    def test_read_limit_returns_latest_events(self):
        with tempfile.TemporaryDirectory() as root:
            for index in range(5):
                self.log.append(
                    root,
                    event_type="test_event",
                    message=f"Event {index}",
                )

            events = self.log.read(
                root,
                limit=2,
            )

        self.assertEqual(
            [event.message for event in events],
            ["Event 3", "Event 4"],
        )

    def test_clear_removes_event_log(self):
        with tempfile.TemporaryDirectory() as root:
            self.log.append(
                root,
                event_type="workflow_started",
                message="Workflow started.",
            )

            self.assertTrue(self.log.clear(root))
            self.assertFalse(
                Path(
                    root,
                    EVENT_LOG_FILENAME,
                ).exists()
            )


if __name__ == "__main__":
    unittest.main()
