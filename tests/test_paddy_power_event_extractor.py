import unittest

from datetime import date, datetime

from app.services.paddy_power_event_extractor import (
    PaddyPowerEventExtractor,
)
from app.services.paddy_power_modus_extractor import (
    KnownBookmakerFixture,
)


class PaddyPowerEventExtractorTests(
    unittest.TestCase
):

    def fixture(self):
        return KnownBookmakerFixture(
            fixture_date=date(
                2026,
                9,
                4,
            ),
            tournament="Czech Darts Open",
            player_a="Ryan Joyce",
            player_b="Kim Huybrechts",
        )

    def test_extracts_total_legs_prices(self):
        html = """
        <html>
          <body>
            <h1>Ryan Joyce v Kim Huybrechts</h1>

            <abc-card class="event-card--item">
              <abc-card-content>
                <abc-accordion>
                  <div class="accordion__header">
                    <span class="accordion__title">
                      Total Legs
                    </span>
                  </div>

                  <section class="accordion__body">
                    <outright-item-list>
                      <outright-item>
                        <p class="outright-item__runner-name">
                          Over (+9.5)
                        </p>
                        <span class="btn-odds__label">
                          5/6
                        </span>
                      </outright-item>

                      <outright-item>
                        <p class="outright-item__runner-name">
                          Under (+9.5)
                        </p>
                        <span class="btn-odds__label">
                          5/6
                        </span>
                      </outright-item>
                    </outright-item-list>
                  </section>
                </abc-accordion>
              </abc-card-content>
            </abc-card>
          </body>
        </html>
        """

        captured_at = datetime(
            2026,
            9,
            4,
            12,
            0,
        )

        extractor = PaddyPowerEventExtractor(
            self.fixture()
        )

        prices = list(
            extractor.extract(
                html,
                captured_at=captured_at,
            )
        )

        self.assertEqual(
            len(prices),
            2,
        )

        self.assertEqual(
            prices[0].market,
            "total_legs",
        )
        self.assertEqual(
            prices[0].selection,
            "Over (+9.5)",
        )
        self.assertAlmostEqual(
            prices[0].decimal_odds,
            1.833333,
            places=6,
        )

        self.assertEqual(
            prices[1].market,
            "total_legs",
        )
        self.assertEqual(
            prices[1].selection,
            "Under (+9.5)",
        )
        self.assertAlmostEqual(
            prices[1].decimal_odds,
            1.833333,
            places=6,
        )

        for price in prices:
            self.assertEqual(
                price.fixture_date,
                date(
                    2026,
                    9,
                    4,
                ),
            )
            self.assertEqual(
                price.tournament,
                "Czech Darts Open",
            )
            self.assertEqual(
                price.player_a,
                "Ryan Joyce",
            )
            self.assertEqual(
                price.player_b,
                "Kim Huybrechts",
            )
            self.assertEqual(
                price.bookmaker,
                "Paddy Power",
            )
            self.assertEqual(
                price.captured_at,
                captured_at,
            )
            self.assertEqual(
                price.provider_id,
                "paddy-power-public-page",
            )


if __name__ == "__main__":
    unittest.main()


class PaddyPowerEventExtractorIsolationTests(
    unittest.TestCase
):

    def test_total_legs_does_not_capture_other_market_prices(self):
        fixture = KnownBookmakerFixture(
            fixture_date=date(
                2026,
                9,
                4,
            ),
            tournament="Czech Darts Open",
            player_a="Ryan Joyce",
            player_b="Kim Huybrechts",
        )

        html = """
        <html>
          <body>
            <abc-card class="event-card--item">
              <abc-card-content>
                <abc-accordion>
                  <div class="accordion__header">
                    <span class="accordion__title">
                      Leg Handicap
                    </span>
                  </div>
                  <section class="accordion__body">
                    <outright-item>
                      <p class="outright-item__runner-name">
                        Ryan Joyce (+1.5)
                      </p>
                      <span class="btn-odds__label">
                        4/6
                      </span>
                    </outright-item>
                    <outright-item>
                      <p class="outright-item__runner-name">
                        Kim Huybrechts (-1.5)
                      </p>
                      <span class="btn-odds__label">
                        11/10
                      </span>
                    </outright-item>
                  </section>
                </abc-accordion>
              </abc-card-content>
            </abc-card>

            <abc-card class="event-card--item">
              <abc-card-content>
                <abc-accordion>
                  <div class="accordion__header">
                    <span class="accordion__title">
                      Total Legs
                    </span>
                  </div>
                  <section class="accordion__body">
                    <outright-item>
                      <p class="outright-item__runner-name">
                        Over (+9.5)
                      </p>
                      <span class="btn-odds__label">
                        5/6
                      </span>
                    </outright-item>
                    <outright-item>
                      <p class="outright-item__runner-name">
                        Under (+9.5)
                      </p>
                      <span class="btn-odds__label">
                        5/6
                      </span>
                    </outright-item>
                  </section>
                </abc-accordion>
              </abc-card-content>
            </abc-card>

            <abc-card class="event-card--item">
              <abc-card-content>
                <abc-accordion>
                  <div class="accordion__header">
                    <span class="accordion__title">
                      Total 180's
                    </span>
                  </div>
                  <section class="accordion__body">
                    <outright-item>
                      <p class="outright-item__runner-name">
                        Over (+4.5)
                      </p>
                      <span class="btn-odds__label">
                        6/5
                      </span>
                    </outright-item>
                    <outright-item>
                      <p class="outright-item__runner-name">
                        Under (+4.5)
                      </p>
                      <span class="btn-odds__label">
                        8/13
                      </span>
                    </outright-item>
                  </section>
                </abc-accordion>
              </abc-card-content>
            </abc-card>
          </body>
        </html>
        """

        prices = list(
            PaddyPowerEventExtractor(
                fixture
            ).extract(
                html,
                captured_at=datetime(
                    2026,
                    9,
                    4,
                    12,
                    0,
                ),
            )
        )

        self.assertEqual(
            [
                (
                    price.market,
                    price.selection,
                    price.decimal_odds,
                )
                for price in prices
            ],
            [
                (
                    "handicap",
                    "Ryan Joyce +1.5",
                    1.666667,
                ),
                (
                    "handicap",
                    "Kim Huybrechts -1.5",
                    2.1,
                ),
                (
                    "total_legs",
                    "Over (+9.5)",
                    1.833333,
                ),
                (
                    "total_legs",
                    "Under (+9.5)",
                    1.833333,
                ),
            ],
        )


class PaddyPowerEventHandicapExtractorTests(
    unittest.TestCase
):

    def test_extracts_leg_handicap_prices(self):
        fixture = KnownBookmakerFixture(
            fixture_date=date(
                2026,
                9,
                4,
            ),
            tournament="Czech Darts Open",
            player_a="Ryan Joyce",
            player_b="Kim Huybrechts",
        )

        html = """
        <html>
          <body>
            <abc-card class="event-card--item">
              <abc-card-content>
                <abc-accordion>
                  <div class="accordion__header">
                    <span class="accordion__title">
                      Leg Handicap
                    </span>
                  </div>

                  <section class="accordion__body">
                    <outright-item-list>
                      <outright-item>
                        <p class="outright-item__runner-name">
                          Ryan Joyce (+1.5)
                        </p>
                        <span class="btn-odds__label">
                          4/6
                        </span>
                      </outright-item>

                      <outright-item>
                        <p class="outright-item__runner-name">
                          Kim Huybrechts (-1.5)
                        </p>
                        <span class="btn-odds__label">
                          11/10
                        </span>
                      </outright-item>
                    </outright-item-list>
                  </section>
                </abc-accordion>
              </abc-card-content>
            </abc-card>
          </body>
        </html>
        """

        prices = list(
            PaddyPowerEventExtractor(
                fixture
            ).extract(
                html,
                captured_at=datetime(
                    2026,
                    9,
                    4,
                    12,
                    0,
                ),
            )
        )

        self.assertEqual(
            [
                (
                    price.market,
                    price.selection,
                    price.decimal_odds,
                )
                for price in prices
            ],
            [
                (
                    "handicap",
                    "Ryan Joyce +1.5",
                    1.666667,
                ),
                (
                    "handicap",
                    "Kim Huybrechts -1.5",
                    2.1,
                ),
            ],
        )
