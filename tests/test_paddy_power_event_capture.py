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


    def test_captures_discovered_event_for_fixture(self):
        from app.services.paddy_power_live_capture import (
            capture_discovered_paddy_power_events,
        )

        fixture = KnownBookmakerFixture(
            fixture_date=date(2026, 9, 4),
            tournament="Czech Darts Open",
            player_a="Ryan Joyce",
            player_b="Kim Huybrechts",
        )

        category_html = """
        <a href="/darts/event/ryan-joyce-v-kim-huybrechts">
          <div>Ryan Joyce</div>
          <div>Kim Huybrechts</div>
        </a>
        """

        event_report = object()
        capture_once = MagicMock(
            return_value=event_report,
        )
        event_service = MagicMock()

        with patch(
            "app.services.paddy_power_live_capture."
            "build_paddy_power_event_capture_once",
            return_value=(
                capture_once,
                event_service,
            ),
        ) as builder:
            db = object()
            reports = capture_discovered_paddy_power_events(
                db,
                fixtures=[fixture],
                category_html=category_html,
            )

        self.assertEqual(
            reports,
            [event_report],
        )

        builder.assert_called_once()

        _, builder_kwargs = builder.call_args

        self.assertEqual(
            builder_kwargs["fixture"],
            fixture,
        )
        self.assertEqual(
            builder_kwargs["source_url"],
            (
                "https:"
                "//www.paddypower.com/darts/event/"
                "ryan-joyce-v-kim-huybrechts"
            ),
        )

        capture_once.assert_called_once_with(db)
        event_service.close.assert_called_once()


    def test_skips_fixture_without_discovered_event_url(self):
        from app.services.paddy_power_live_capture import (
            capture_discovered_paddy_power_events,
        )

        fixture = KnownBookmakerFixture(
            fixture_date=date(2026, 9, 4),
            tournament="Czech Darts Open",
            player_a="Ryan Joyce",
            player_b="Kim Huybrechts",
        )

        category_html = """
        <a href="/darts/event/player-one-v-player-two">
          <div>Player One</div>
          <div>Player Two</div>
        </a>
        """

        with patch(
            "app.services.paddy_power_live_capture."
            "build_paddy_power_event_capture_once",
        ) as builder:
            reports = capture_discovered_paddy_power_events(
                object(),
                fixtures=[fixture],
                category_html=category_html,
            )

        self.assertEqual(
            reports,
            [],
        )
        builder.assert_not_called()


if __name__ == "__main__":
    unittest.main()
