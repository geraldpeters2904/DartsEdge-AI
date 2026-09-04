import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from app.services.paddy_power_modus_extractor import (
    KnownBookmakerFixture,
)


class PaddyPowerEventCaptureTests(unittest.TestCase):

    def test_builder_captures_event_url_with_event_extractor(self):
        from app.services.paddy_power_live_capture import (
            build_paddy_power_event_capture_once,
        )

        fixture = KnownBookmakerFixture(
            fixture_date=date(2026, 9, 4),
            tournament="Czech Darts Open",
            player_a="Ryan Joyce",
            player_b="Kim Huybrechts",
        )

        source_url = (
            "https:"
            "//www.paddypower.com/darts/event/"
            "ryan-joyce-v-kim-huybrechts"
        )

        service = MagicMock()
        service.capture.return_value = object()

        with patch(
            "app.services.paddy_power_live_capture."
            "PaddyPowerCaptureService",
            return_value=service,
        ):
            capture_once, returned_service = (
                build_paddy_power_event_capture_once(
                    fixture=fixture,
                    source_url=source_url,
                )
            )

        db = object()
        result = capture_once(db)

        self.assertIs(
            returned_service,
            service,
        )
        self.assertIs(
            result,
            service.capture.return_value,
        )

        service.capture.assert_called_once()

        args, kwargs = service.capture.call_args

        self.assertEqual(
            args,
            (db,),
        )
        self.assertEqual(
            kwargs["source_url"],
            source_url,
        )

        extractor = kwargs["extractor"]

        self.assertEqual(
            extractor.fixture,
            fixture,
        )
        self.assertEqual(
            extractor.__class__.__name__,
            "PaddyPowerEventExtractor",
        )


if __name__ == "__main__":
    unittest.main()
