from __future__ import annotations

import html
import re
from typing import Iterable, List

from app.providers.adapters.modus_official.schemas import (
    ModusMatchDetailRecord,
    ModusMatchListRecord,
    ModusPlayerMatchStats,
)


_MATCH_LINK = re.compile(
    r"(?:match-db-stats\.php\?match_id=|/match/statistics/)(\d+)",
    re.IGNORECASE,
)


class ModusSavedPageParser:
    """
    Parse saved or pasted MODUS HTML.

    Pack 1 deliberately avoids live HTTP requests. Parsing is tolerant and
    raises a clear structure-change error when expected source markers vanish.
    """

    def discover_match_ids(self, html_text: str) -> List[int]:
        ids = []
        seen = set()
        for value in _MATCH_LINK.findall(html_text or ""):
            match_id = int(value)
            if match_id not in seen:
                seen.add(match_id)
                ids.append(match_id)
        return ids

    def parse_results_page(self, html_text: str) -> List[ModusMatchListRecord]:
        """
        Parse test-fixture match cards marked with data attributes.

        Production page-specific selectors will be added after representative
        saved official pages are captured and sanitised.
        """
        records = []
        pattern = re.compile(
            r'<[^>]+data-match-id="(?P<id>\d+)"'
            r'[^>]+data-player-a="(?P<a>[^"]+)"'
            r'[^>]+data-player-b="(?P<b>[^"]+)"'
            r'(?:[^>]+data-player-a-legs="(?P<al>\d+)")?'
            r'(?:[^>]+data-player-b-legs="(?P<bl>\d+)")?'
            r'[^>]*>',
            re.IGNORECASE,
        )
        for match in pattern.finditer(html_text or ""):
            records.append(
                ModusMatchListRecord(
                    match_id=int(match.group("id")),
                    player_a_name=html.unescape(match.group("a")).strip(),
                    player_b_name=html.unescape(match.group("b")).strip(),
                    player_a_legs=_optional_int(match.group("al")),
                    player_b_legs=_optional_int(match.group("bl")),
                )
            )

        if not records and self.discover_match_ids(html_text):
            raise ValueError(
                "MODUS match links were found, but Pack 1 could not parse "
                "the surrounding match cards. Capture a saved page fixture "
                "before adding production selectors."
            )
        return records

    def parse_match_detail(self, html_text: str) -> ModusMatchDetailRecord:
        values = _data_attributes(html_text)
        required = (
            "match-id",
            "player-a",
            "player-b",
            "player-a-legs",
            "player-b-legs",
        )
        missing = [name for name in required if name not in values]
        if missing:
            raise ValueError(
                "Saved MODUS match page is missing required markers: "
                + ", ".join(missing)
            )

        return ModusMatchDetailRecord(
            match_id=int(values["match-id"]),
            player_a_name=values["player-a"],
            player_b_name=values["player-b"],
            player_a_legs=int(values["player-a-legs"]),
            player_b_legs=int(values["player-b-legs"]),
            player_a_stats=_player_stats(values, "player-a"),
            player_b_stats=_player_stats(values, "player-b"),
            series_label=values.get("series"),
            group=values.get("group"),
        )


def _data_attributes(text: str) -> dict[str, str]:
    result = {}
    for name, value in re.findall(
        r'data-([a-z0-9-]+)="([^"]*)"',
        text or "",
        flags=re.IGNORECASE,
    ):
        result[name.lower()] = html.unescape(value).strip()
    return result


def _player_stats(values: dict[str, str], prefix: str) -> ModusPlayerMatchStats:
    return ModusPlayerMatchStats(
        player_name=values[prefix],
        three_dart_average=_optional_float(values.get(f"{prefix}-average")),
        scores_100_plus=_optional_int(values.get(f"{prefix}-100-plus")),
        scores_140_plus=_optional_int(values.get(f"{prefix}-140-plus")),
        scores_180=_optional_int(values.get(f"{prefix}-180s")),
        checkout_attempts=_optional_int(
            values.get(f"{prefix}-checkout-attempts")
        ),
        checkouts_completed=_optional_int(
            values.get(f"{prefix}-checkouts-completed")
        ),
        checkout_percentage=_optional_float(
            values.get(f"{prefix}-checkout-percentage")
        ),
        highest_checkout=_optional_int(
            values.get(f"{prefix}-highest-checkout")
        ),
        ton_plus_checkouts=_optional_int(
            values.get(f"{prefix}-ton-plus-checkouts")
        ),
    )


def _optional_int(value):
    return None if value in (None, "") else int(value)


def _optional_float(value):
    return None if value in (None, "") else float(value)
