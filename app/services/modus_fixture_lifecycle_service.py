from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import html
import re
from typing import List, Optional

from app.providers.adapters.modus_official.identifiers import (
    modus_match_external_id,
    modus_player_external_id,
    modus_source_external_id,
)
from app.schemas.canonical import (
    CanonicalFixture,
    CompetitionCode,
    MatchStatus,
    RecordConfidence,
    SourceReference,
)


PROVIDER = "modus-official"
COMPETITION_NAME = "MODUS Super Series"


@dataclass(frozen=True)
class ModusFixtureCard:
    match_id: int
    match_number: Optional[int]
    player_a_name: str
    player_b_name: str
    player_a_legs: Optional[int]
    player_b_legs: Optional[int]
    status: MatchStatus
    series_id: int
    series_label: str
    week_id: int
    week_label: str
    group: str
    scheduled_at: Optional[datetime] = None


@dataclass(frozen=True)
class FixtureLifecyclePreview:
    fixtures: List[CanonicalFixture]

    @property
    def scheduled_count(self) -> int:
        return sum(
            1 for fixture in self.fixtures
            if fixture.status == MatchStatus.SCHEDULED
        )

    @property
    def completed_count(self) -> int:
        return sum(
            1 for fixture in self.fixtures
            if fixture.status == MatchStatus.COMPLETED
        )

    def to_dict(self) -> dict:
        return {
            "fixture_count": len(self.fixtures),
            "scheduled_count": self.scheduled_count,
            "completed_count": self.completed_count,
        }


class ModusFixtureLifecycleService:
    """
    Parse completed and upcoming MODUS fixture cards from saved results HTML.

    No live requests are performed. Scheduled fixtures never receive fabricated
    result/statistics values. Where MODUS does not expose a scheduled datetime,
    the canonical fixture receives the deterministic build timestamp required
    by the existing CanonicalFixture schema.
    """

    def parse_cards(self, html_text: str) -> List[ModusFixtureCard]:
        text = html_text or ""
        series_id, series_label = self._selected_option(
            text,
            "seriesSelect",
            "Series",
        )
        week_id, week_label = self._selected_option(
            text,
            "weekSelect",
            "Week",
        )
        group = self._selected_group(text)

        cards: List[ModusFixtureCard] = []
        article_pattern = re.compile(
            r"<article(?P<attrs>[^>]*)>(?P<body>.*?)</article>",
            re.IGNORECASE | re.DOTALL,
        )

        for article in article_pattern.finditer(text):
            attrs = article.group("attrs")
            body = article.group("body")

            match_id_match = re.search(
                r"match-db-stats\.php\?match_id=(\d+)",
                attrs + body,
                flags=re.IGNORECASE,
            )
            upcoming = "fixture-card-upcoming" in attrs.lower()
            source_game_match = re.search(
                r'data-source-game-number="(\d+)"',
                attrs,
                flags=re.IGNORECASE,
            )
            if match_id_match:
                match_id = int(match_id_match.group(1))
            elif upcoming and source_game_match:
                match_id = int(source_game_match.group(1))
            else:
                continue

            rows = re.findall(
                r'<div[^>]*class="player-row"[^>]*>\s*'
                r'<span[^>]*class="score"[^>]*>(.*?)</span>\s*'
                r"<span[^>]*>(.*?)</span>\s*</div>",
                body,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if len(rows) != 2:
                raise ValueError(
                    f"Unable to parse two players for match "
                    f"{match_id}."
                )

            match_number_match = re.search(
                r'<div[^>]*class="match-label"[^>]*>\s*'
                r"(?:Match\s+)?(\d+)",
                body,
                flags=re.IGNORECASE | re.DOTALL,
            )

            score_a = self._optional_score(rows[0][0], upcoming=upcoming)
            score_b = self._optional_score(rows[1][0], upcoming=upcoming)

            status = (
                MatchStatus.SCHEDULED
                if upcoming or score_a is None or score_b is None
                else MatchStatus.COMPLETED
            )

            cards.append(
                ModusFixtureCard(
                    match_id=match_id,
                    match_number=(
                        int(match_number_match.group(1))
                        if match_number_match else None
                    ),
                    player_a_name=self._clean(rows[0][1]),
                    player_b_name=self._clean(rows[1][1]),
                    player_a_legs=score_a,
                    player_b_legs=score_b,
                    status=status,
                    series_id=series_id,
                    series_label=series_label,
                    week_id=week_id,
                    week_label=week_label,
                    group=group,
                )
            )

        if not cards:
            raise ValueError("No MODUS fixture cards were found.")

        return cards

    def build_canonical_fixtures(
        self,
        html_text: str,
    ) -> FixtureLifecyclePreview:
        cards = self.parse_cards(html_text)
        retrieved_at = datetime.utcnow()
        fixtures: List[CanonicalFixture] = []

        for card in cards:
            match_external_id = modus_match_external_id(card.match_id)
            player_a_id = modus_player_external_id(card.player_a_name)
            player_b_id = modus_player_external_id(card.player_b_name)

            source = SourceReference(
                provider=PROVIDER,
                external_id=modus_source_external_id(
                    "fixture",
                    match_id=card.match_id,
                ),
                retrieved_at=retrieved_at,
                competition_code=CompetitionCode.MODUS,
                confidence=RecordConfidence.VERIFIED,
            )

            fixture_time = card.scheduled_at or retrieved_at

            fixtures.append(
                CanonicalFixture(
                    external_id=match_external_id,
                    competition_code=CompetitionCode.MODUS,
                    competition_name=COMPETITION_NAME,
                    series=card.series_label,
                    week=card.week_label,
                    group=card.group,
                    stage=card.group,
                    scheduled_at=fixture_time,
                    actual_start_at=(
                        fixture_time
                        if card.status == MatchStatus.COMPLETED
                        else None
                    ),
                    status=card.status,
                    match_format="Best of 7",
                    player_a_external_id=player_a_id,
                    player_a_name=card.player_a_name,
                    player_b_external_id=player_b_id,
                    player_b_name=card.player_b_name,
                    source=source,
                )
            )

        return FixtureLifecyclePreview(fixtures=fixtures)

    @staticmethod
    def lifecycle_action(
        *,
        existing_status: Optional[MatchStatus],
        incoming_status: MatchStatus,
    ) -> str:
        if existing_status is None:
            return "insert"

        if (
            existing_status == MatchStatus.SCHEDULED
            and incoming_status == MatchStatus.COMPLETED
        ):
            return "update"

        if existing_status == incoming_status:
            return "skip"

        if (
            existing_status == MatchStatus.COMPLETED
            and incoming_status == MatchStatus.SCHEDULED
        ):
            return "reject"

        return "update"

    @staticmethod
    def _selected_option(
        text: str,
        select_id: str,
        fallback_prefix: str,
    ) -> tuple[int, str]:
        select_match = re.search(
            rf'<select[^>]+id="{re.escape(select_id)}"[^>]*>'
            rf"(?P<body>.*?)</select>",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not select_match:
            raise ValueError(f"Missing {select_id} selector.")

        option_match = re.search(
            r'<option[^>]+value="(\d+)"[^>]*selected[^>]*>(.*?)</option>',
            select_match.group("body"),
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not option_match:
            raise ValueError(f"No selected option in {select_id}.")

        value = int(option_match.group(1))
        label = ModusFixtureLifecycleService._clean(option_match.group(2))
        if not label:
            label = f"{fallback_prefix} {value}"
        return value, label

    @staticmethod
    def _selected_group(text: str) -> str:
        match = re.search(
            r'<button[^>]+class="active"[^>]*>\s*(Group\s+[ABC]|Final)\s*</button>',
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            raise ValueError("Unable to determine selected MODUS group.")
        value = ModusFixtureLifecycleService._clean(match.group(1))
        return "Final" if value.lower() == "final" else value.title()

    @staticmethod
    def _optional_score(value: str, *, upcoming: bool) -> Optional[int]:
        if upcoming:
            return None
        cleaned = ModusFixtureLifecycleService._clean(value)
        if cleaned == "":
            return None
        return int(cleaned)

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(
            r"\s+",
            " ",
            html.unescape(re.sub(r"<[^>]+>", "", value or "")),
        ).strip()
