from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Optional

from app.providers.adapters.modus_official.schemas import (
    ModusMatchDetailRecord,
    ModusPlayerMatchStats,
)


class ModusRealMatchPageParser:
    """Parse genuine saved MODUS match-statistics HTML offline."""

    REQUIRED_STATS = {
        "average",
        "100+",
        "140+",
        "180s",
        "checkouts",
        "checkout %",
        "high checkout",
        "ton+ checkouts",
    }

    def parse(
        self,
        html_text: str,
        *,
        match_id: Optional[int] = None,
    ) -> ModusMatchDetailRecord:
        if not (html_text or "").strip():
            raise ValueError("Saved MODUS match page is blank.")

        parser = _DocumentParser()
        parser.feed(html_text)
        parser.close()

        if match_id is None:
            raise ValueError(
                "The saved MODUS match page does not expose match_id in "
                "its HTML. Pass match_id explicitly from the source URL "
                "or saved file name."
            )
        match_id = int(match_id)
        if match_id <= 0:
            raise ValueError("match_id must be greater than zero.")

        if len(parser.players) != 2:
            raise ValueError(
                "Saved MODUS match page does not contain exactly two players."
            )
        if len(parser.scores) != 2:
            raise ValueError(
                "Saved MODUS match page does not contain a complete score."
            )
        if not parser.series_label:
            raise ValueError(
                "Saved MODUS match page does not contain a Series label."
            )
        if not parser.group:
            raise ValueError(
                "Saved MODUS match page does not contain a Group label."
            )

        missing = self.REQUIRED_STATS - set(parser.stat_rows)
        if missing:
            raise ValueError(
                "Saved MODUS match page is missing statistics: "
                + ", ".join(sorted(missing))
            )

        player_a, player_b = parser.players
        stats_a = _build_stats(player_a, 0, parser.stat_rows)
        stats_b = _build_stats(player_b, 1, parser.stat_rows)

        return ModusMatchDetailRecord(
            match_id=match_id,
            player_a_name=player_a,
            player_b_name=player_b,
            player_a_legs=parser.scores[0],
            player_b_legs=parser.scores[1],
            player_a_stats=stats_a,
            player_b_stats=stats_b,
            played_at=parser.played_at,
            series_label=parser.series_label,
            week_label=parser.week_label,
            group=parser.group,
        )


class _DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.players = []
        self.scores = []
        self.stat_rows = {}
        self.played_at = None
        self.series_label = None
        self.week_label = None
        self.group = None

        self._capture = None
        self._buffer = []
        self._in_score_area = False
        self._in_meta = False
        self._row = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())

        if tag == "div" and "meta" in classes:
            self._in_meta = True
        elif tag == "a" and self._in_meta and "tab" in classes:
            self._start_capture("meta")
        elif tag == "p" and "mobile-date" in classes:
            self._start_capture("date")
        elif tag == "div" and "player-name" in classes:
            self._start_capture("player")
        elif tag == "div" and "score-area" in classes:
            self._in_score_area = True
        elif tag == "span" and self._in_score_area:
            self._start_capture("score")
        elif tag == "div" and "stat-row" in classes:
            self._row = {"left": None, "label": None, "right": None}
        elif tag == "div" and self._row is not None:
            if "stat-left" in classes:
                self._start_capture("left")
            elif "stat-label" in classes:
                self._start_capture("label")
            elif "stat-right" in classes:
                self._start_capture("right")

    def handle_data(self, data):
        if self._capture:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if self._capture and (
            (self._capture in {"meta"} and tag == "a")
            or (self._capture == "date" and tag == "p")
            or (self._capture in {"player", "left", "label", "right"} and tag == "div")
            or (self._capture == "score" and tag == "span")
        ):
            kind = self._capture
            value = _clean(self._buffer)
            self._capture = None
            self._buffer = []
            self._finish_capture(kind, value)

        if tag == "div" and self._in_score_area:
            self._in_score_area = False

        if tag == "div" and self._row is not None and all(
            self._row.get(key) is not None for key in ("left", "label", "right")
        ):
            label = _normalise_label(self._row["label"])
            self.stat_rows[label] = (self._row["left"], self._row["right"])
            self._row = None

        if tag == "div" and self._in_meta:
            self._in_meta = False

    def _start_capture(self, kind):
        self._capture = kind
        self._buffer = []

    def _finish_capture(self, kind, value):
        if not value:
            return
        if kind == "meta":
            if value.lower() == "back":
                return
            if value.startswith("Series "):
                self.series_label = value
            elif value.startswith("Week "):
                self.week_label = value
            elif value.startswith("Group ") or value == "Final":
                self.group = value
            elif "/" in value and self.played_at is None:
                self.played_at = _parse_datetime(value)
        elif kind == "date" and self.played_at is None:
            self.played_at = _parse_datetime(value)
        elif kind == "player":
            self.players.append(value)
        elif kind == "score":
            self.scores.append(int(value))
        elif kind in {"left", "label", "right"} and self._row is not None:
            self._row[kind] = value


def _build_stats(player_name, index, rows):
    completed, attempts = _parse_fraction(rows["checkouts"][index])
    percentage = _parse_percentage(rows["checkout %"][index])
    calculated = round(completed / attempts * 100, 2) if attempts else 0.0
    if abs(calculated - percentage) > 0.1:
        raise ValueError(
            f"Checkout percentage for {player_name} does not match "
            "completed/attempted checkouts."
        )

    return ModusPlayerMatchStats(
        player_name=player_name,
        three_dart_average=_parse_average(rows["average"][index]),
        scores_100_plus=int(rows["100+"][index]),
        scores_140_plus=int(rows["140+"][index]),
        scores_180=int(rows["180s"][index]),
        checkout_attempts=attempts,
        checkouts_completed=completed,
        checkout_percentage=percentage,
        highest_checkout=int(rows["high checkout"][index]),
        ton_plus_checkouts=int(rows["ton+ checkouts"][index]),
    )


def _parse_fraction(value):
    match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", value or "")
    if not match:
        raise ValueError("Checkouts must use completed/attempted format.")
    completed, attempts = int(match.group(1)), int(match.group(2))
    if completed > attempts:
        raise ValueError("Completed checkouts cannot exceed attempts.")
    return completed, attempts


def _parse_percentage(value):
    result = float((value or "").replace("%", "").strip())
    if not 0 <= result <= 100:
        raise ValueError("Checkout percentage must be between 0 and 100.")
    return result


def _parse_average(value):
    result = float((value or "").replace(" ", "").strip())
    if not 0 <= result <= 180:
        raise ValueError("Three-dart average must be between 0 and 180.")
    return result


def _parse_datetime(value):
    text = " ".join((value or "").split())
    for fmt in ("%d %b %Y / %H:%M", "%d %b %Y %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError(f"Unsupported MODUS date/time format: {value!r}")


def _normalise_label(value):
    return " ".join((value or "").lower().split())


def _clean(parts):
    return " ".join("".join(parts).split())
