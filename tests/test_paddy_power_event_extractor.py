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


    def test_extracts_match_odds_prices(self):
        html = """
        <html>
          <body>
            <abc-card class="event-card--item">
              <abc-card-content>
                <abc-accordion>
                  <div class="accordion__header">
                    <span class="accordion__title">
                      Match Odds
                    </span>
                  </div>
                  <section class="accordion__body">
                    <outright-item-list>
                      <outright-item>
                        <p class="outright-item__runner-name">
                          Ryan Joyce
                        </p>
                        <span class="btn-odds__label">
                          4/5
                        </span>
                      </outright-item>
                      <outright-item>
                        <p class="outright-item__runner-name">
                          Kim Huybrechts
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
                self.fixture()
            ).extract(
                html,
                captured_at=datetime(
                    2026, 9, 4, 12, 0
                ),
            )
        )

        self.assertEqual(
            [
                (
                    price.market,
                    price.selection,
                    round(
                        price.decimal_odds,
                        6,
                    ),
                )
                for price in prices
            ],
            [
                (
                    "match_winner",
                    "Ryan Joyce",
                    1.8,
                ),
                (
                    "match_winner",
                    "Kim Huybrechts",
                    2.1,
                ),
            ],
        )


    def test_extracts_live_horizontal_match_odds_prices(self):
        html = """
        <html>
          <body>
            <abc-card class="event-card--item">
              <abc-card-content>
                <abc-accordion>
                  <div class="accordion__header">
                    <span class="accordion__title">
                      Match Odds
                    </span>
                  </div>
                  <section class="accordion__body">
                    <abc-sub-header>
                      <div class="subheader">
                        <div class="subheader__text--subtitle">
                          Ryan Joyce
                        </div>
                        <div class="subheader__text--subtitle">
                          Kim Huybrechts
                        </div>
                      </div>
                    </abc-sub-header>
                    <horizontal-buttons>
                      <div class="horizontal-buttons">
                        <abc-btn-odds>
                          <span class="btn-odds__label">
                            4/5
                          </span>
                        </abc-btn-odds>
                        <abc-btn-odds>
                          <span class="btn-odds__label">
                            11/10
                          </span>
                        </abc-btn-odds>
                      </div>
                    </horizontal-buttons>
                  </section>
                </abc-accordion>
              </abc-card-content>
            </abc-card>
          </body>
        </html>
        """

        prices = list(
            PaddyPowerEventExtractor(
                self.fixture()
            ).extract(
                html,
                captured_at=datetime(
                    2026, 9, 4, 12, 0
                ),
            )
        )

        self.assertEqual(
            [
                (
                    price.market,
                    price.selection,
                    round(
                        price.decimal_odds,
                        6,
                    ),
                )
                for price in prices
            ],
            [
                (
                    "match_winner",
                    "Ryan Joyce",
                    1.8,
                ),
                (
                    "match_winner",
                    "Kim Huybrechts",
                    2.1,
                ),
            ],
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
                (
                    "total_180s",
                    "Over (+4.5)",
                    2.2,
                ),
                (
                    "total_180s",
                    "Under (+4.5)",
                    1.615385,
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


class PaddyPowerEvent180ExtractorTests(
    unittest.TestCase
):

    def test_extracts_live_180_market_shapes(self):
        fixture = KnownBookmakerFixture(
            fixture_date=date(
                2026,
                9,
                4,
            ),
            tournament="MODUS Super Series",
            player_a="Danny Goddard",
            player_b="Mark Layton",
        )

        html = """
        <html>
          <body>
            <abc-card class="event-card--item">
              <span class="accordion__title">
                Most 180's
              </span>
              <p class="outright-item__runner-name">
                Danny Goddard
              </p>
              <span class="btn-odds__label">11/10</span>
              <p class="outright-item__runner-name">
                Draw
              </p>
              <span class="btn-odds__label">7/5</span>
              <p class="outright-item__runner-name">
                Mark Layton
              </p>
              <span class="btn-odds__label">4/1</span>
            </abc-card>

            <abc-card class="event-card--item">
              <span class="accordion__title">
                Total 180's
              </span>
              <p class="outright-item__runner-name">
                Over (+1.5)
              </p>
              <span class="btn-odds__label">6/4</span>
              <p class="outright-item__runner-name">
                Under (+1.5)
              </p>
              <span class="btn-odds__label">1/2</span>
            </abc-card>

            <abc-card class="event-card--item">
              <span class="accordion__title">
                Danny Goddard Total 180's
              </span>
              <p class="outright-item__runner-name">
                Over (+0.5)
              </p>
              <span class="btn-odds__label">4/7</span>
              <p class="outright-item__runner-name">
                Under (+0.5)
              </p>
              <span class="btn-odds__label">5/4</span>
            </abc-card>

            <abc-card class="event-card--item">
              <span class="accordion__title">
                Mark Layton Total 180's
              </span>
              <p class="outright-item__runner-name">
                Over (+0.5)
              </p>
              <span class="btn-odds__label">13/8</span>
              <p class="outright-item__runner-name">
                Under (+0.5)
              </p>
              <span class="btn-odds__label">4/9</span>
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

        actual = [
            (
                price.market,
                price.selection,
                price.decimal_odds,
            )
            for price in prices
        ]

        expected = [
            (
                "most_180s",
                "Danny Goddard",
                2.1,
            ),
            (
                "most_180s",
                "Draw",
                2.4,
            ),
            (
                "most_180s",
                "Mark Layton",
                5.0,
            ),
            (
                "total_180s",
                "Over (+1.5)",
                2.5,
            ),
            (
                "total_180s",
                "Under (+1.5)",
                1.5,
            ),
            (
                "player_total_180s",
                "Danny Goddard | Over (+0.5)",
                1.571429,
            ),
            (
                "player_total_180s",
                "Danny Goddard | Under (+0.5)",
                2.25,
            ),
            (
                "player_total_180s",
                "Mark Layton | Over (+0.5)",
                2.625,
            ),
            (
                "player_total_180s",
                "Mark Layton | Under (+0.5)",
                1.444444,
            ),
        ]

        self.assertEqual(
            actual,
            expected,
        )
