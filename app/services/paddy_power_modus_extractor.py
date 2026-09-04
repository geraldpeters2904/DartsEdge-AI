from __future__ import annotations

import re

from urllib.parse import urljoin
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Iterable, Sequence

from app.services.bookmaker_capture_types import (
    CapturedBookmakerPrice,
)


_ODDS_RE = re.compile(
    r"^(?:\d+(?:\.\d+)?|\d+/\d+|EVS|EVENS?)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class KnownBookmakerFixture:
    fixture_date: date
    tournament: str
    player_a: str
    player_b: str


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._ignore_depth = 0
        self.tokens: list[str] = []

    def handle_starttag(
        self,
        tag,
        attrs,
    ):
        if tag in {
            "script",
            "style",
            "noscript",
            "svg",
        }:
            self._ignore_depth += 1

    def handle_endtag(
        self,
        tag,
    ):
        if (
            tag
            in {
                "script",
                "style",
                "noscript",
                "svg",
            }
            and self._ignore_depth
            > 0
        ):
            self._ignore_depth -= 1

    def handle_data(
        self,
        data,
    ):
        if self._ignore_depth:
            return

        cleaned = " ".join(
            data.split()
        )

        if cleaned:
            self.tokens.append(
                cleaned
            )


class _FixtureEventLinkParser(HTMLParser):

    def __init__(self) -> None:
        super().__init__()
        self._active_href = None
        self._active_tokens: list[str] = []
        self.links: list[
            tuple[str, tuple[str, ...]]
        ] = []

    def handle_starttag(
        self,
        tag,
        attrs,
    ):
        if tag != "a":
            return

        href = dict(
            attrs
        ).get(
            "href"
        )

        if not href:
            return

        self._active_href = href
        self._active_tokens = []

    def handle_data(
        self,
        data,
    ):
        if self._active_href is None:
            return

        cleaned = " ".join(
            data.split()
        )

        if cleaned:
            self._active_tokens.append(
                cleaned
            )

    def handle_endtag(
        self,
        tag,
    ):
        if (
            tag != "a"
            or self._active_href is None
        ):
            return

        self.links.append(
            (
                self._active_href,
                tuple(
                    self._active_tokens
                ),
            )
        )

        self._active_href = None
        self._active_tokens = []


def discover_fixture_event_url(
    html: str,
    fixture: KnownBookmakerFixture,
) -> str | None:
    parser = _FixtureEventLinkParser()
    parser.feed(
        html or ""
    )

    player_a = normalise_name(
        fixture.player_a
    )
    player_b = normalise_name(
        fixture.player_b
    )

    for href, tokens in parser.links:
        normalised_tokens = {
            normalise_name(
                token
            )
            for token in tokens
        }

        if (
            player_a in normalised_tokens
            and player_b in normalised_tokens
        ):
            return urljoin(
                "https:" + "//www.paddypower.com",
                href,
            )

    return None


def visible_text_tokens(
    html: str,
) -> tuple[str, ...]:
    parser = _VisibleTextParser()
    parser.feed(
        html or ""
    )

    return tuple(
        parser.tokens
    )


def normalise_name(
    value: str,
) -> str:
    return " ".join(
        (value or "")
        .strip()
        .casefold()
        .split()
    )


def decimal_odds(
    value: str,
) -> float:
    text = (
        (value or "")
        .strip()
        .upper()
    )

    if text in {
        "EVS",
        "EVEN",
        "EVENS",
    }:
        return 2.0

    if "/" in text:
        left, right = (
            text.split(
                "/",
                1,
            )
        )

        numerator = float(
            left
        )
        denominator = float(
            right
        )

        if denominator <= 0:
            raise ValueError(
                "Fractional odds denominator must be positive."
            )

        return round(
            1.0
            + numerator
            / denominator,
            6,
        )

    numeric = float(
        text
    )

    if numeric <= 1.0:
        raise ValueError(
            "Decimal odds must be greater than 1.00."
        )

    return numeric


def _looks_like_odds(
    value: str,
) -> bool:
    return bool(
        _ODDS_RE.match(
            (value or "").strip()
        )
    )


def _find_fixture_window(
    tokens: Sequence[str],
    fixture: KnownBookmakerFixture,
) -> tuple[int, int] | None:
    player_a = normalise_name(
        fixture.player_a
    )
    player_b = normalise_name(
        fixture.player_b
    )

    for index, token in enumerate(
        tokens
    ):
        if normalise_name(
            token
        ) != player_a:
            continue

        end = min(
            len(
                tokens
            ),
            index + 10,
        )

        for second in range(
            index + 1,
            end,
        ):
            if normalise_name(
                tokens[
                    second
                ]
            ) == player_b:
                return (
                    index,
                    second,
                )

    return None


def _extract_match_odds(
    tokens: Sequence[str],
    *,
    player_b_index: int,
) -> tuple[
    float,
    float,
] | None:
    candidates = []

    end = min(
        len(
            tokens
        ),
        player_b_index + 12,
    )

    for token in tokens[
        player_b_index
        + 1:end
    ]:
        if not _looks_like_odds(
            token
        ):
            continue

        try:
            value = decimal_odds(
                token
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

        candidates.append(
            value
        )

        if len(
            candidates
        ) == 2:
            return (
                candidates[0],
                candidates[1],
            )

    return None


class PaddyPowerModusExtractor:
    """
    Extract Match Winner prices from the public Paddy Power MODUS page.

    The extractor intentionally avoids CSS-class dependencies.
    It matches known DartsEdge fixtures by player names, then reads the
    first two odds tokens immediately following the two selections.

    Additional market extractors can be layered on later after we have
    captured representative event-page HTML.
    """

    BOOKMAKER = "Paddy Power"

    def __init__(
        self,
        fixtures: Iterable[
            KnownBookmakerFixture
        ],
    ) -> None:
        self.fixtures = tuple(
            fixtures
        )

    def extract(
        self,
        html: str,
        *,
        captured_at: datetime,
    ) -> Iterable[
        CapturedBookmakerPrice
    ]:
        tokens = visible_text_tokens(
            html
        )

        prices = []

        for fixture in self.fixtures:
            window = (
                _find_fixture_window(
                    tokens,
                    fixture,
                )
            )

            if window is None:
                continue

            _, player_b_index = (
                window
            )

            odds = (
                _extract_match_odds(
                    tokens,
                    player_b_index=(
                        player_b_index
                    ),
                )
            )

            if odds is None:
                continue

            odds_a, odds_b = (
                odds
            )

            prices.extend([
                CapturedBookmakerPrice(
                    fixture_date=(
                        fixture
                        .fixture_date
                    ),
                    tournament=(
                        fixture
                        .tournament
                        or "MODUS"
                    ),
                    player_a=(
                        fixture.player_a
                    ),
                    player_b=(
                        fixture.player_b
                    ),
                    market=(
                        "match_winner"
                    ),
                    selection=(
                        fixture.player_a
                    ),
                    bookmaker=(
                        self.BOOKMAKER
                    ),
                    decimal_odds=(
                        odds_a
                    ),
                    captured_at=(
                        captured_at
                    ),
                    provider_id=(
                        "paddy-power-public-page"
                    ),
                ),
                CapturedBookmakerPrice(
                    fixture_date=(
                        fixture
                        .fixture_date
                    ),
                    tournament=(
                        fixture
                        .tournament
                        or "MODUS"
                    ),
                    player_a=(
                        fixture.player_a
                    ),
                    player_b=(
                        fixture.player_b
                    ),
                    market=(
                        "match_winner"
                    ),
                    selection=(
                        fixture.player_b
                    ),
                    bookmaker=(
                        self.BOOKMAKER
                    ),
                    decimal_odds=(
                        odds_b
                    ),
                    captured_at=(
                        captured_at
                    ),
                    provider_id=(
                        "paddy-power-public-page"
                    ),
                ),
            ])

        return prices
