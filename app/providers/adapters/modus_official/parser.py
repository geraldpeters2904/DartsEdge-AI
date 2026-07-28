from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import List, Optional

from app.providers.adapters.modus_official.schemas import (
    ModusGroupTableRecord,
    ModusMatchDetailRecord,
    ModusMatchListRecord,
    ModusPlayerMatchStats,
    ModusResultsPageRecord,
)


_MATCH_LINK = re.compile(
    r"(?:match-db-stats\.php\?match_id=|/match/statistics/)(\d+)",
    re.IGNORECASE,
)
_MATCH_NUMBER = re.compile(r"match\s+(\d+)", re.IGNORECASE)
_GROUP_CALL = re.compile(r"changeGroup\(['\"]([^'\"]+)['\"]\)", re.IGNORECASE)


class ModusSavedPageParser:
    """
    Parse saved or pasted MODUS HTML without making any network requests.

    The real-results parser uses Python's HTMLParser and therefore works with
    the document tree rather than matching the complete page with one large
    regular expression. The original Pack 1 data-attribute fixture remains
    supported for backwards compatibility.
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

    def parse_results_document(
        self,
        html_text: str,
    ) -> ModusResultsPageRecord:
        if not (html_text or "").strip():
            raise ValueError("Saved MODUS results page is blank.")

        parser = _ResultsDocumentParser()
        parser.feed(html_text)
        parser.close()

        if parser.selected_series is None:
            raise ValueError(
                "Saved MODUS results page has no selected Series option."
            )
        if parser.selected_week is None:
            raise ValueError(
                "Saved MODUS results page has no selected Week option."
            )
        if not parser.active_group:
            raise ValueError(
                "Saved MODUS results page has no active group tab."
            )
        if not parser.matches:
            if self.discover_match_ids(html_text):
                raise ValueError(
                    "MODUS match links were found, but no fixture cards "
                    "could be parsed. The page structure may have changed."
                )
            raise ValueError(
                "No MODUS fixture cards were found on the saved page."
            )

        match_ids = [record.match_id for record in parser.matches]
        if len(match_ids) != len(set(match_ids)):
            raise ValueError(
                "The saved MODUS results page contains duplicate match IDs."
            )

        series_id, series_label = parser.selected_series
        week_id, week_label = parser.selected_week

        matches = [
            ModusMatchListRecord(
                match_id=record.match_id,
                player_a_name=record.player_a_name,
                player_b_name=record.player_b_name,
                player_a_legs=record.player_a_legs,
                player_b_legs=record.player_b_legs,
                series_label=series_label,
                week_label=week_label,
                group=parser.active_group,
                match_number=record.match_number,
            )
            for record in parser.matches
        ]

        return ModusResultsPageRecord(
            series_id=series_id,
            series_label=series_label,
            week_id=week_id,
            week_label=week_label,
            group=parser.active_group,
            matches=matches,
            group_table=parser.group_table,
        )

    def parse_results_page(
        self,
        html_text: str,
    ) -> List[ModusMatchListRecord]:
        """
        Return match records from either genuine MODUS HTML or the original
        Pack 1 synthetic data-attribute fixture.
        """
        if 'id="seriesSelect"' in (html_text or ""):
            return self.parse_results_document(html_text).matches

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
                "MODUS match links were found, but the surrounding match "
                "cards could not be parsed."
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


class _ResultsDocumentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current_select: Optional[str] = None
        self.option_value: Optional[str] = None
        self.option_selected = False
        self.option_text: List[str] = []
        self.selected_series: Optional[tuple[int, str]] = None
        self.selected_week: Optional[tuple[int, str]] = None

        self.button_active = False
        self.button_group: Optional[str] = None
        self.button_text: List[str] = []
        self.active_group: Optional[str] = None

        self.current_match: Optional[dict] = None
        self.match_label_text: List[str] = []
        self.in_match_label = False
        self.in_player_row = False
        self.current_span_class = ""
        self.current_span_text: List[str] = []
        self.matches: List[ModusMatchListRecord] = []

        self.in_table_row = False
        self.table_cells: List[tuple[str, str]] = []
        self.current_table_cell_class: Optional[str] = None
        self.current_table_cell_text: List[str] = []
        self.group_table: List[ModusGroupTableRecord] = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        classes = set((attr.get("class") or "").split())

        if tag == "select":
            select_id = attr.get("id")
            if select_id in {"seriesSelect", "weekSelect"}:
                self.current_select = select_id

        elif tag == "option" and self.current_select:
            self.option_value = attr.get("value")
            self.option_selected = "selected" in attr
            self.option_text = []

        elif tag == "button":
            onclick = attr.get("onclick") or ""
            match = _GROUP_CALL.search(onclick)
            if match:
                self.button_group = match.group(1).strip()
                self.button_active = "active" in classes
                self.button_text = []

        elif tag == "article" and "fixture-card" in classes:
            onclick = attr.get("onclick") or ""
            match = _MATCH_LINK.search(onclick)
            self.current_match = {
                "match_id": int(match.group(1)) if match else None,
                "players": [],
                "scores": [],
                "match_number": None,
            }

        elif self.current_match is not None:
            if tag == "div" and "match-label" in classes:
                self.in_match_label = True
                self.match_label_text = []
            elif tag == "div" and "player-row" in classes:
                self.in_player_row = True
            elif tag == "span" and self.in_player_row:
                self.current_span_class = attr.get("class") or ""
                self.current_span_text = []

        if tag == "div" and "table-row" in classes:
            self.in_table_row = True
            self.table_cells = []
        elif (
            tag == "div"
            and self.in_table_row
            and classes.intersection({"position", "name", "stat", "points"})
        ):
            self.current_table_cell_class = next(
                name
                for name in ("position", "name", "stat", "points")
                if name in classes
            )
            self.current_table_cell_text = []

    def handle_data(self, data):
        if self.option_value is not None:
            self.option_text.append(data)
        if self.button_group is not None:
            self.button_text.append(data)
        if self.in_match_label:
            self.match_label_text.append(data)
        if self.current_span_class or (
            self.in_player_row and self.current_span_text is not None
        ):
            self.current_span_text.append(data)
        if self.current_table_cell_class is not None:
            self.current_table_cell_text.append(data)

    def handle_endtag(self, tag):
        if tag == "option" and self.option_value is not None:
            label = _clean_text(self.option_text)
            if self.option_selected and label:
                value = _required_int(self.option_value, "selected option")
                if self.current_select == "seriesSelect":
                    self.selected_series = (value, label)
                elif self.current_select == "weekSelect":
                    self.selected_week = (value, label)
            self.option_value = None
            self.option_selected = False
            self.option_text = []

        elif tag == "select":
            self.current_select = None

        elif tag == "button" and self.button_group is not None:
            if self.button_active:
                self.active_group = self.button_group
            self.button_group = None
            self.button_active = False
            self.button_text = []

        elif tag == "div" and self.in_match_label:
            text = _clean_text(self.match_label_text)
            match = _MATCH_NUMBER.search(text)
            if self.current_match is not None and match:
                self.current_match["match_number"] = int(match.group(1))
            self.in_match_label = False
            self.match_label_text = []

        elif tag == "span" and self.in_player_row:
            value = _clean_text(self.current_span_text)
            if self.current_match is not None and value:
                if "score" in self.current_span_class.split():
                    self.current_match["scores"].append(_optional_int(value))
                else:
                    self.current_match["players"].append(value)
            self.current_span_class = ""
            self.current_span_text = []

        elif tag == "div" and self.in_player_row:
            self.in_player_row = False

        elif tag == "article" and self.current_match is not None:
            self._finish_match()
            self.current_match = None

        if tag == "div" and self.current_table_cell_class is not None:
            value = _clean_text(self.current_table_cell_text)
            self.table_cells.append(
                (self.current_table_cell_class, value)
            )
            self.current_table_cell_class = None
            self.current_table_cell_text = []
        elif tag == "div" and self.in_table_row:
            self._finish_table_row()
            self.in_table_row = False
            self.table_cells = []

    def _finish_match(self):
        match_id = self.current_match["match_id"]
        players = self.current_match["players"]
        scores = self.current_match["scores"]

        if match_id is None:
            raise ValueError("A MODUS fixture card has no match_id.")
        if len(players) != 2:
            raise ValueError(
                f"MODUS match {match_id} does not contain two players."
            )
        if len(scores) not in {0, 2}:
            raise ValueError(
                f"MODUS match {match_id} has an incomplete score."
            )
        if players[0] == players[1]:
            raise ValueError(
                f"MODUS match {match_id} contains the same player twice."
            )

        self.matches.append(
            ModusMatchListRecord(
                match_id=match_id,
                player_a_name=players[0],
                player_b_name=players[1],
                player_a_legs=scores[0] if scores else None,
                player_b_legs=scores[1] if scores else None,
                match_number=self.current_match["match_number"],
            )
        )

    def _finish_table_row(self):
        if not self.table_cells:
            return

        values = [value for _, value in self.table_cells]
        classes = [name for name, _ in self.table_cells]
        if "position" not in classes or "name" not in classes:
            return

        position = values[classes.index("position")]
        player_name = values[classes.index("name")]
        stats = [
            value
            for class_name, value in self.table_cells
            if class_name == "stat"
        ]
        points_values = [
            value
            for class_name, value in self.table_cells
            if class_name == "points"
        ]

        if len(stats) != 5 or len(points_values) != 1:
            raise ValueError(
                f"MODUS group-table row for {player_name!r} has "
                "an unexpected column layout."
            )

        self.group_table.append(
            ModusGroupTableRecord(
                position=_required_int(position, "position"),
                player_name=player_name,
                played=_required_int(stats[0], "played"),
                won=_required_int(stats[1], "won"),
                lost=_required_int(stats[2], "lost"),
                leg_difference=_required_int(
                    stats[3],
                    "leg_difference",
                ),
                three_dart_average=float(stats[4]),
                points=_required_int(points_values[0], "points"),
            )
        )


def _clean_text(parts) -> str:
    return " ".join("".join(parts).split())


def _required_int(value, field_name: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc


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
