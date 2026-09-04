from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
from typing import Iterable

from app.services.bookmaker_capture_types import (
    CapturedBookmakerPrice,
)
from app.services.paddy_power_modus_extractor import (
    KnownBookmakerFixture,
    decimal_odds,
)


def _classes(
    attrs,
) -> set[str]:
    for name, value in attrs:
        if name == "class":
            return set(
                (value or "").split()
            )
    return set()


class _EventMarketParser(
    HTMLParser
):

    def __init__(
        self,
    ) -> None:
        super().__init__()

        self._card_depth = 0
        self._capture_title_depth = 0
        self._capture_runner_depth = 0
        self._capture_subtitle_depth = 0
        self._capture_odds_depth = 0

        self._title_parts: list[str] = []
        self._runner_parts: list[str] = []
        self._subtitle_parts: list[str] = []
        self._odds_parts: list[str] = []

        self._current_title = ""
        self._current_runner = ""
        self._subtitles: list[str] = []
        self._subtitle_index = 0

        self.markets: list[
            tuple[
                str,
                list[
                    tuple[
                        str,
                        str,
                    ]
                ],
            ]
        ] = []

        self._current_prices: list[
            tuple[
                str,
                str,
            ]
        ] = []

    def handle_starttag(
        self,
        tag,
        attrs,
    ):
        classes = _classes(
            attrs
        )

        if self._card_depth:
            self._card_depth += 1
        elif (
            tag == "abc-card"
            and "event-card--item"
            in classes
        ):
            self._card_depth = 1
            self._current_title = ""
            self._current_runner = ""
            self._subtitles = []
            self._subtitle_index = 0
            self._current_prices = []

        if not self._card_depth:
            return

        if "accordion__title" in classes:
            self._capture_title_depth = 1
            self._title_parts = []
        elif self._capture_title_depth:
            self._capture_title_depth += 1

        if (
            "outright-item__runner-name"
            in classes
        ):
            self._capture_runner_depth = 1
            self._runner_parts = []
        elif self._capture_runner_depth:
            self._capture_runner_depth += 1

        if "subheader__text--subtitle" in classes:
            self._capture_subtitle_depth = 1
            self._subtitle_parts = []
        elif self._capture_subtitle_depth:
            self._capture_subtitle_depth += 1

        if "btn-odds__label" in classes:
            self._capture_odds_depth = 1
            self._odds_parts = []
        elif self._capture_odds_depth:
            self._capture_odds_depth += 1

    def handle_endtag(
        self,
        tag,
    ):
        if not self._card_depth:
            return

        if self._capture_title_depth:
            self._capture_title_depth -= 1
            if not self._capture_title_depth:
                self._current_title = " ".join(
                    " ".join(
                        self._title_parts
                    ).split()
                )

        if self._capture_runner_depth:
            self._capture_runner_depth -= 1
            if not self._capture_runner_depth:
                self._current_runner = " ".join(
                    " ".join(
                        self._runner_parts
                    ).split()
                )

        if self._capture_subtitle_depth:
            self._capture_subtitle_depth -= 1
            if not self._capture_subtitle_depth:
                subtitle = " ".join(
                    " ".join(
                        self._subtitle_parts
                    ).split()
                )
                if subtitle:
                    self._subtitles.append(subtitle)

        if self._capture_odds_depth:
            self._capture_odds_depth -= 1
            if not self._capture_odds_depth:
                odds = " ".join(
                    " ".join(
                        self._odds_parts
                    ).split()
                )
                runner = self._current_runner
                if (
                    not runner
                    and self._subtitle_index < len(self._subtitles)
                ):
                    runner = self._subtitles[
                        self._subtitle_index
                    ]
                    self._subtitle_index += 1

                if runner and odds:
                    self._current_prices.append(
                        (
                            runner,
                            odds,
                        )
                    )
                    self._current_runner = ""

        self._card_depth -= 1

        if not self._card_depth:
            if self._current_title:
                self.markets.append(
                    (
                        self._current_title,
                        list(
                            self._current_prices
                        ),
                    )
                )

            self._current_title = ""
            self._current_runner = ""
            self._subtitles = []
            self._subtitle_index = 0
            self._current_prices = []

    def handle_data(
        self,
        data,
    ):
        if self._capture_title_depth:
            self._title_parts.append(
                data
            )

        if self._capture_runner_depth:
            self._runner_parts.append(
                data
            )

        if self._capture_subtitle_depth:
            self._subtitle_parts.append(
                data
            )

        if self._capture_odds_depth:
            self._odds_parts.append(
                data
            )


class PaddyPowerEventExtractor:

    BOOKMAKER = "Paddy Power"

    PROVIDER_ID = (
        "paddy-power-public-page"
    )

    def __init__(
        self,
        fixture: KnownBookmakerFixture,
    ) -> None:
        self.fixture = fixture

    def extract(
        self,
        html: str,
        *,
        captured_at: datetime,
    ) -> Iterable[
        CapturedBookmakerPrice
    ]:
        parser = _EventMarketParser()
        parser.feed(
            html or ""
        )

        prices = []

        for market_name, runners in (
            parser.markets
        ):
            normalised_market = " ".join(
                market_name
                .strip()
                .casefold()
                .split()
            )

            market_map = {
                "match odds": "match_winner",
                "total legs": "total_legs",
                "leg handicap": "handicap",
                "most 180's": "most_180s",
                "total 180's": "total_180s",
            }

            market = market_map.get(
                normalised_market
            )

            player_total_180s_player = None

            if market is None:
                for player in (
                    self.fixture.player_a,
                    self.fixture.player_b,
                ):
                    player_market = " ".join(
                        (
                            f"{player} Total 180's"
                        )
                        .casefold()
                        .split()
                    )

                    if (
                        normalised_market
                        == player_market
                    ):
                        market = (
                            "player_total_180s"
                        )
                        player_total_180s_player = (
                            player
                        )
                        break

            if market is None:
                continue

            for selection, raw_odds in runners:
                if (
                    market
                    == "player_total_180s"
                    and player_total_180s_player
                ):
                    selection = (
                        f"{player_total_180s_player}"
                        f" | {selection}"
                    )

                if market == "handicap":
                    for player in (
                        self.fixture.player_a,
                        self.fixture.player_b,
                    ):
                        prefix = f"{player} ("
                        if (
                            selection.startswith(prefix)
                            and selection.endswith(")")
                        ):
                            line_text = selection[
                                len(prefix):-1
                            ]
                            try:
                                line = float(
                                    line_text
                                )
                            except ValueError:
                                line = None

                            if (
                                line is not None
                                and line != 0
                                and abs(line) % 1 == 0.5
                                and line_text
                                == f"{line:+.1f}"
                            ):
                                selection = (
                                    f"{player} "
                                    f"{line:+.1f}"
                                )
                            break

                try:
                    odds = decimal_odds(
                        raw_odds
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

                prices.append(
                    CapturedBookmakerPrice(
                        fixture_date=(
                            self.fixture
                            .fixture_date
                        ),
                        tournament=(
                            self.fixture
                            .tournament
                        ),
                        player_a=(
                            self.fixture
                            .player_a
                        ),
                        player_b=(
                            self.fixture
                            .player_b
                        ),
                        market=market,
                        selection=selection,
                        bookmaker=(
                            self.BOOKMAKER
                        ),
                        decimal_odds=odds,
                        captured_at=(
                            captured_at
                        ),
                        provider_id=(
                            self.PROVIDER_ID
                        ),
                    )
                )

        return prices
