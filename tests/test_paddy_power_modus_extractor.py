import unittest
from datetime import date, datetime

from app.services.paddy_power_modus_extractor import (
    KnownBookmakerFixture,
    PaddyPowerModusExtractor,
    decimal_odds,
    visible_text_tokens,
)


class PaddyPowerModusExtractorTests(
    unittest.TestCase
):
    def fixture(self):
        return KnownBookmakerFixture(
            fixture_date=date(
                2026,
                8,
                7,
            ),
            tournament="MODUS",
            player_a="Steve West",
            player_b="Andreas Harrysson",
        )

    def test_fractional_odds_convert_to_decimal(self):
        self.assertAlmostEqual(
            decimal_odds(
                "8/13"
            ),
            1.6153846,
            places=5,
        )

        self.assertEqual(
            decimal_odds(
                "EVS"
            ),
            2.0,
        )

    def test_visible_parser_ignores_script(self):
        tokens = (
            visible_text_tokens(
                """
                <html>
                  <script>Fake Player 99/1</script>
                  <div>Steve West</div>
                </html>
                """
            )
        )

        self.assertIn(
            "Steve West",
            tokens,
        )

        self.assertNotIn(
            "Fake Player 99/1",
            tokens,
        )

    def test_extracts_match_winner_prices(self):
        html = """
        <html>
          <body>
            <h1>MODUS Super Series</h1>
            <div>Matches</div>
            <div>Steve West</div>
            <div>Andreas Harrysson</div>
            <span>8/13</span>
            <span>6/5</span>
            <time>11:10</time>
          </body>
        </html>
        """

        extractor = (
            PaddyPowerModusExtractor([
                self.fixture()
            ])
        )

        prices = list(
            extractor.extract(
                html,
                captured_at=datetime(
                    2026,
                    8,
                    7,
                    10,
                    0,
                ),
            )
        )

        self.assertEqual(
            len(
                prices
            ),
            2,
        )

        self.assertEqual(
            prices[0].selection,
            "Steve West",
        )

        self.assertAlmostEqual(
            prices[0].decimal_odds,
            1.6153846,
            places=5,
        )

        self.assertEqual(
            prices[1].selection,
            "Andreas Harrysson",
        )

        self.assertEqual(
            prices[1].decimal_odds,
            2.2,
        )

    def test_ignores_unknown_fixture(self):
        html = """
        <div>Player One</div>
        <div>Player Two</div>
        <span>4/6</span>
        <span>11/10</span>
        """

        extractor = (
            PaddyPowerModusExtractor([
                self.fixture()
            ])
        )

        prices = list(
            extractor.extract(
                html,
                captured_at=datetime(
                    2026,
                    8,
                    7,
                    10,
                    0,
                ),
            )
        )

        self.assertEqual(
            prices,
            [],
        )


    def test_discovers_event_url_for_known_fixture(self):
        from app.services.paddy_power_modus_extractor import (
            discover_fixture_event_url,
        )

        html = """
        <html>
          <body>
            <a href="https://www.paddypower.com/darts/event/steve-west-v-andreas-harrysson">
              <div>Steve West</div>
              <div>Andreas Harrysson</div>
              <span>8/13</span>
              <span>6/5</span>
            </a>
          </body>
        </html>
        """

        source_url = discover_fixture_event_url(
            html,
            self.fixture(),
        )

        self.assertEqual(
            source_url,
            (
                "https://www.paddypower.com/darts/event/"
                "steve-west-v-andreas-harrysson"
            ),
        )


    def test_discovers_absolute_url_from_relative_event_link(self):
        from app.services.paddy_power_modus_extractor import (
            discover_fixture_event_url,
        )

        html = """
        <a href="/darts/event/steve-west-v-andreas-harrysson">
          <div>Steve West</div>
          <div>Andreas Harrysson</div>
        </a>
        """

        source_url = discover_fixture_event_url(
            html,
            self.fixture(),
        )

        self.assertEqual(
            source_url,
            (
                "https://www.paddypower.com/darts/event/"
                "steve-west-v-andreas-harrysson"
            ),
        )


    def test_does_not_mix_players_from_different_event_links(self):
        from app.services.paddy_power_modus_extractor import (
            discover_fixture_event_url,
        )

        html = """
        <html>
          <body>
            <a href="/darts/event/steve-west-v-player-one">
              <div>Steve West</div>
              <div>Player One</div>
            </a>

            <a href="/darts/event/player-two-v-andreas-harrysson">
              <div>Player Two</div>
              <div>Andreas Harrysson</div>
            </a>
          </body>
        </html>
        """

        source_url = discover_fixture_event_url(
            html,
            self.fixture(),
        )

        self.assertIsNone(
            source_url,
        )


if __name__ == "__main__":
    unittest.main()
