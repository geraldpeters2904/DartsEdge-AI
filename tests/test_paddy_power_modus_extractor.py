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


if __name__ == "__main__":
    unittest.main()
