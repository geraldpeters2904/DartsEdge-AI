import unittest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from app.services.paddy_power_modus_extractor import (
    KnownBookmakerFixture,
)


class PaddyPowerCategoryReadyTests(
    unittest.TestCase
):
    def test_requires_rendered_modus_fixture_link(self):
        from app.services.paddy_power_live_capture import (
            paddy_power_modus_category_ready,
        )

        shell_html = (
            "<html>"
            "Sports Darts Login Sign Up"
            "</html>"
        )

        rendered_html = (
            "<html>"
            "<a href=\"/darts/modus-super-series/"
            "justin-smith-v-danny-goddard-36029048\">"
            "<span>Justin Smith</span>"
            "<span>Danny Goddard</span>"
            "</a>"
            "</html>"
        )

        self.assertFalse(
            paddy_power_modus_category_ready(
                shell_html
            )
        )

        self.assertTrue(
            paddy_power_modus_category_ready(
                rendered_html
            )
        )


class PaddyPowerCategoryLoadTests(
    unittest.TestCase
):
    def test_loads_rendered_modus_category_html(self):
        from app.services.paddy_power_live_capture import (
            PADDY_POWER_MODUS_URL,
            load_paddy_power_modus_category_html,
            paddy_power_modus_category_ready,
        )

        rendered_html = (
            "<html>"
            "<a href=\"/darts/modus-super-series/"
            "justin-smith-v-danny-goddard-36029048\">"
            "<span>Justin Smith</span>"
            "<span>Danny Goddard</span>"
            "</a>"
            "</html>"
        )

        browser = MagicMock()
        browser.html.return_value = rendered_html

        with patch(
            "app.services.paddy_power_live_capture."
            "ChromeBrowserSession",
            return_value=browser,
        ):
            result = (
                load_paddy_power_modus_category_html()
            )

        browser.goto.assert_called_once_with(
            PADDY_POWER_MODUS_URL,
            timeout_seconds=30.0,
        )

        browser.wait_for.assert_called_once()

        args, kwargs = browser.wait_for.call_args
        predicate = args[0]

        self.assertTrue(
            predicate()
        )
        self.assertTrue(
            paddy_power_modus_category_ready(
                rendered_html
            )
        )

        self.assertEqual(
            kwargs["timeout_seconds"],
            30.0,
        )
        self.assertEqual(
            kwargs["description"],
            "rendered Paddy Power MODUS fixtures",
        )

        self.assertEqual(
            result,
            rendered_html,
        )

        browser.close.assert_called_once()


class PaddyPowerDiscoveredCaptureOnceTests(
    unittest.TestCase
):
    def test_loads_category_and_captures_discovered_events(self):
        from app.services.paddy_power_live_capture import (
            capture_paddy_power_discovered_events_once,
        )

        fixture = KnownBookmakerFixture(
            fixture_date=date(2026, 9, 4),
            tournament="MODUS",
            player_a="Justin Smith",
            player_b="Danny Goddard",
        )

        category_html = (
            "<html>"
            "<a href=\"/darts/modus-super-series/"
            "justin-smith-v-danny-goddard-36029048\">"
            "<span>Justin Smith</span>"
            "<span>Danny Goddard</span>"
            "</a>"
            "</html>"
        )

        reports = [
            object(),
        ]

        db = object()

        with patch(
            "app.services.paddy_power_live_capture."
            "_scheduled_modus_fixtures",
            return_value=[fixture],
        ) as scheduled:
            with patch(
                "app.services.paddy_power_live_capture."
                "load_paddy_power_modus_category_html",
                return_value=category_html,
            ) as loader:
                with patch(
                    "app.services.paddy_power_live_capture."
                    "capture_discovered_paddy_power_events",
                    return_value=reports,
                ) as capture_events:
                    result = (
                        capture_paddy_power_discovered_events_once(
                            db
                        )
                    )

        self.assertEqual(
            result,
            reports,
        )

        scheduled.assert_called_once_with(
            db
        )

        loader.assert_called_once_with()

        capture_events.assert_called_once_with(
            db,
            fixtures=[fixture],
            category_html=category_html,
        )


class PaddyPowerDiscoveredAggregateCaptureTests(
    unittest.TestCase
):

    def test_aggregates_discovered_event_reports(self):
        from app.services.bookmaker_capture_types import (
            BookmakerCaptureReport,
        )
        from app.services.paddy_power_live_capture import (
            capture_paddy_power_discovered_events_report_once,
        )

        first_report = BookmakerCaptureReport(
            bookmaker="Paddy Power",
            source_url="event-one",
            captured_at=datetime(2026, 9, 4, 10, 0),
            extracted_prices=13,
            stored_prices=10,
            unchanged_prices=3,
            skipped_prices=0,
            challenge_detected=False,
            message="first",
        )

        second_report = BookmakerCaptureReport(
            bookmaker="Paddy Power",
            source_url="event-two",
            captured_at=datetime(2026, 9, 4, 10, 1),
            extracted_prices=13,
            stored_prices=8,
            unchanged_prices=4,
            skipped_prices=1,
            challenge_detected=True,
            message="second",
        )

        db = object()

        with patch(
            "app.services.paddy_power_live_capture."
            "capture_paddy_power_discovered_events_once",
            return_value=[
                first_report,
                second_report,
            ],
        ) as capture_events:
            report = (
                capture_paddy_power_discovered_events_report_once(
                    db
                )
            )

        capture_events.assert_called_once_with(db)

        self.assertEqual(
            report.bookmaker,
            "Paddy Power",
        )
        self.assertEqual(
            report.extracted_prices,
            26,
        )
        self.assertEqual(
            report.stored_prices,
            18,
        )
        self.assertEqual(
            report.unchanged_prices,
            7,
        )
        self.assertEqual(
            report.skipped_prices,
            1,
        )
        self.assertTrue(
            report.challenge_detected
        )



class PaddyPowerLiveRunnerTests(
    unittest.TestCase
):

    def test_live_runner_uses_discovered_event_aggregate_capture(self):
        from app.services.paddy_power_live_capture import (
            run_paddy_power_live_capture,
        )

        manager = MagicMock()
        manager.run_forever.return_value = (
            "manager-status"
        )

        with patch(
            "app.services.paddy_power_live_capture."
            "BookmakerCaptureManager",
            return_value=manager,
        ) as manager_class:
            result = (
                run_paddy_power_live_capture(
                    max_cycles=1,
                )
            )

        self.assertEqual(
            result,
            "manager-status",
        )

        _, manager_kwargs = (
            manager_class.call_args
        )

        from app.services.paddy_power_live_capture import (
            capture_paddy_power_discovered_events_report_once,
        )

        self.assertIs(
            manager_kwargs["capture_once"],
            capture_paddy_power_discovered_events_report_once,
        )

        manager.run_forever.assert_called_once()



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


    def test_builder_waits_for_rendered_event_cards(self):
        from app.services.paddy_power_live_capture import (
            build_paddy_power_event_capture_once,
        )

        fixture = KnownBookmakerFixture(
            fixture_date=date(2026, 9, 4),
            tournament="MODUS Super Series",
            player_a="Jordan Brooks",
            player_b="Justin Smith",
        )

        service = MagicMock()
        service.capture.return_value = object()

        with patch(
            "app.services.paddy_power_live_capture."
            "PaddyPowerCaptureService",
            return_value=service,
        ):
            capture_once, _ = (
                build_paddy_power_event_capture_once(
                    fixture=fixture,
                    source_url=(
                        "https:"
                        "//www.paddypower.com/darts/"
                        "modus-super-series/"
                        "jordan-brooks-v-justin-smith-36029022"
                    ),
                )
            )

        capture_once(object())

        _, kwargs = service.capture.call_args

        self.assertIn(
            "page_ready",
            kwargs,
        )

        predicate = kwargs["page_ready"]

        shell_html = (
            "<html>"
            "Sports Darts Login Sign Up"
            "</html>"
        )

        rendered_html = (
            '<html>'
            '<abc-card class="event-card--item">'
            '<div>Match Odds</div>'
            '</abc-card>'
            '</html>'
        )

        self.assertFalse(
            predicate(shell_html)
        )

        self.assertTrue(
            predicate(rendered_html)
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



    def test_continues_after_event_capture_failure(self):
        from app.services.paddy_power_live_capture import (
            capture_discovered_paddy_power_events,
        )

        first_fixture = KnownBookmakerFixture(
            fixture_date=date(2026, 9, 4),
            tournament="MODUS Super Series",
            player_a="Player One",
            player_b="Player Two",
        )

        second_fixture = KnownBookmakerFixture(
            fixture_date=date(2026, 9, 4),
            tournament="MODUS Super Series",
            player_a="Player Three",
            player_b="Player Four",
        )

        category_html = """
        <a href="/darts/event/player-one-v-player-two">
          <div>Player One</div>
          <div>Player Two</div>
        </a>
        <a href="/darts/event/player-three-v-player-four">
          <div>Player Three</div>
          <div>Player Four</div>
        </a>
        """

        first_capture = MagicMock(
            side_effect=TimeoutError(
                "event page timed out"
            )
        )
        second_report = object()
        second_capture = MagicMock(
            return_value=second_report
        )

        first_service = MagicMock()
        second_service = MagicMock()

        builder_results = [
            (
                first_capture,
                first_service,
            ),
            (
                second_capture,
                second_service,
            ),
        ]

        db = MagicMock()

        with patch(
            "app.services.paddy_power_live_capture."
            "build_paddy_power_event_capture_once",
            side_effect=builder_results,
        ):
            reports = (
                capture_discovered_paddy_power_events(
                    db,
                    fixtures=[
                        first_fixture,
                        second_fixture,
                    ],
                    category_html=category_html,
                )
            )

        self.assertEqual(
            reports,
            [second_report],
        )

        db.rollback.assert_called_once()

        first_service.close.assert_called_once()
        second_service.close.assert_called_once()

        first_capture.assert_called_once_with(db)
        second_capture.assert_called_once_with(db)



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
