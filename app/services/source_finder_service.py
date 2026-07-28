from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


ENTITY_TYPES: Tuple[Tuple[str, str], ...] = (
    ("fixtures", "Fixtures"),
    ("results", "Results"),
    ("statistics", "Statistics"),
    ("odds", "Odds"),
)


@dataclass(frozen=True)
class ResearchSource:
    source_id: str
    name: str
    url: str
    source_kind: str
    trust_level: str
    access_method: str
    coverage: Tuple[str, ...]
    notes: str
    preferred_for: Tuple[str, ...] = ()

    def supports(self, entity_type: str) -> bool:
        return entity_type in self.coverage

    def to_dict(self) -> Dict[str, object]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "url": self.url,
            "source_kind": self.source_kind,
            "trust_level": self.trust_level,
            "access_method": self.access_method,
            "coverage": list(self.coverage),
            "notes": self.notes,
            "preferred_for": list(self.preferred_for),
        }


SOURCES: Tuple[ResearchSource, ...] = (
    ResearchSource(
        source_id="modus-official",
        name="MODUS Super Series — Official Match Centre",
        url="https://modussuperseries.com/",
        source_kind="official",
        trust_level="high",
        access_method="Open the match centre and copy visible fixtures or results.",
        coverage=("fixtures", "results"),
        preferred_for=("fixtures", "results"),
        notes=(
            "Use as the primary identity and scheduling reference. The visible "
            "match centre may not expose every detailed statistic or historical price."
        ),
    ),
    ResearchSource(
        source_id="livesport-modus",
        name="Livesport — MODUS Super Series",
        url="https://www.livesport.com/uk/darts/world/modus-super-series/",
        source_kind="results-aggregator",
        trust_level="medium",
        access_method="Open Fixtures, Results or Odds, then copy the relevant table.",
        coverage=("fixtures", "results", "statistics", "odds"),
        preferred_for=("statistics",),
        notes=(
            "Useful secondary source for live results, fixture lists, match detail and "
            "odds comparison. Verify important values against another source."
        ),
    ),
    ResearchSource(
        source_id="flashscore-modus",
        name="Flashscore UK — MODUS Super Series",
        url="https://www.flashscore.co.uk/darts/world/modus-super-series/",
        source_kind="results-aggregator",
        trust_level="medium",
        access_method="Open Fixtures, Results or Odds and copy the displayed rows.",
        coverage=("fixtures", "results", "odds"),
        preferred_for=("fixtures",),
        notes=(
            "Good cross-check for schedules, results and prices. Some detailed match "
            "statistics may only be visible inside individual match pages."
        ),
    ),
    ResearchSource(
        source_id="betfair-modus",
        name="Betfair Sportsbook — MODUS Super Series",
        url="https://www.betfair.com/betting/darts",
        source_kind="bookmaker",
        trust_level="medium",
        access_method="Search MODUS Super Series and copy current match-result prices.",
        coverage=("odds",),
        preferred_for=("odds",),
        notes=(
            "Use for current bookmaker prices only. Record the capture time and retain "
            "the bookmaker name with every observation."
        ),
    ),
)


class SourceFinderService:
    """Curated catalogue and coverage planner for MODUS research."""

    entity_types = ENTITY_TYPES

    def sources(self, entity_type: Optional[str] = None) -> List[ResearchSource]:
        if entity_type:
            self._validate_entity_type(entity_type)
            return [source for source in SOURCES if source.supports(entity_type)]
        return list(SOURCES)

    def source(self, source_id: str) -> Optional[ResearchSource]:
        return next((item for item in SOURCES if item.source_id == source_id), None)

    def coverage_plan(self) -> Dict[str, List[ResearchSource]]:
        return {
            entity_type: sorted(
                self.sources(entity_type),
                key=lambda source: (
                    entity_type not in source.preferred_for,
                    source.trust_level != "high",
                    source.name,
                ),
            )
            for entity_type, _ in ENTITY_TYPES
        }

    def missing_coverage(self) -> List[str]:
        plan = self.coverage_plan()
        return [entity_type for entity_type, sources in plan.items() if not sources]

    @staticmethod
    def _validate_entity_type(entity_type: str) -> None:
        valid = {value for value, _ in ENTITY_TYPES}
        if entity_type not in valid:
            raise ValueError(f"Unsupported source-finder entity type: {entity_type}")
