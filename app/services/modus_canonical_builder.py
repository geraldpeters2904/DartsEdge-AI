from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from app.collector.csv_definitions import allowed_headers
from app.providers.adapters.modus_official.identifiers import (
    modus_match_external_id,
    modus_player_external_id,
    modus_source_external_id,
)
from app.providers.adapters.modus_official.parser import ModusSavedPageParser
from app.providers.adapters.modus_official.real_match_parser import (
    ModusRealMatchPageParser,
)
from app.schemas.canonical import (
    CanonicalFixture,
    CanonicalMatchResult,
    CanonicalPlayerMatchStatistics,
    CompetitionCode,
    MatchStatus,
    RecordConfidence,
    SourceReference,
)
from app.services.modus_folder_service import (
    ModusFolderImportService,
    ModusFolderManifest,
)


PROVIDER = "modus-official"
COMPETITION_NAME = "MODUS Super Series"


@dataclass(frozen=True)
class ModusCanonicalBuild:
    manifest: ModusFolderManifest
    fixtures: List[CanonicalFixture]
    results: List[CanonicalMatchResult]
    statistics: List[CanonicalPlayerMatchStatistics]
    csv_by_type: Dict[str, str]
    filenames: Dict[str, str]

    @property
    def ready(self) -> bool:
        return (
            bool(self.fixtures)
            and len(self.fixtures) == len(self.results)
            and len(self.statistics) == len(self.fixtures) * 2
        )

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "fixture_count": len(self.fixtures),
            "result_count": len(self.results),
            "statistics_count": len(self.statistics),
            "filenames": dict(self.filenames),
            "manifest": self.manifest.to_dict(),
        }


class ModusCanonicalBuilder:
    """Build validated canonical records and in-memory CSV from a ready folder."""

    def __init__(self):
        self.folder_service = ModusFolderImportService()
        self.results_parser = ModusSavedPageParser()
        self.match_parser = ModusRealMatchPageParser()

    def build(
        self,
        folder: str | Path,
        *,
        allow_partial: bool = False,
    ) -> ModusCanonicalBuild:
        manifest = self.folder_service.inspect(
            folder,
            allow_partial=allow_partial,
        )
        accepted = (
            manifest.partial_ready
            if allow_partial
            else manifest.ready
        )
        if not accepted:
            mode = "partial acceptance" if allow_partial else "full"
            raise ValueError(
                f"MODUS folder is not ready for {mode} canonical build. "
                "Resolve all manifest errors first."
            )
        if manifest.results_file is None:
            raise ValueError("Ready manifest unexpectedly has no results file.")

        page = self.results_parser.parse_results_document(
            manifest.results_file.read_text(encoding="utf-8")
        )

        listed_by_id = {match.match_id: match for match in page.matches}

        fixtures: List[CanonicalFixture] = []
        results: List[CanonicalMatchResult] = []
        statistics: List[CanonicalPlayerMatchStatistics] = []

        selected_match_ids = (
            manifest.validated_match_ids
            if allow_partial
            else manifest.expected_match_ids
        )

        for match_id in selected_match_ids:
            listed = listed_by_id[match_id]
            detail_path = manifest.folder / f"match_{match_id}.html"
            detail = self.match_parser.parse(
                detail_path.read_text(encoding="utf-8"),
                match_id=match_id,
            )

            if detail.played_at is None:
                raise ValueError(
                    f"match_{match_id}.html has no usable match date/time."
                )

            match_external_id = modus_match_external_id(match_id)
            player_a_id = modus_player_external_id(detail.player_a_name)
            player_b_id = modus_player_external_id(detail.player_b_name)
            winner_id = (
                player_a_id
                if detail.player_a_legs > detail.player_b_legs
                else player_b_id
            )
            retrieved_at = datetime.utcnow()

            fixture_source = SourceReference(
                provider=PROVIDER,
                external_id=modus_source_external_id(
                    "fixture",
                    match_id=match_id,
                ),
                retrieved_at=retrieved_at,
                competition_code=CompetitionCode.MODUS,
                confidence=RecordConfidence.VERIFIED,
            )
            result_source = SourceReference(
                provider=PROVIDER,
                external_id=modus_source_external_id(
                    "result",
                    match_id=match_id,
                ),
                retrieved_at=retrieved_at,
                competition_code=CompetitionCode.MODUS,
                confidence=RecordConfidence.VERIFIED,
            )

            fixture = CanonicalFixture(
                external_id=match_external_id,
                competition_code=CompetitionCode.MODUS,
                competition_name=COMPETITION_NAME,
                series=page.series_label,
                week=page.week_label,
                group=page.group,
                stage=page.group,
                scheduled_at=detail.played_at,
                actual_start_at=detail.played_at,
                status=MatchStatus.COMPLETED,
                match_format="Best of 7",
                player_a_external_id=player_a_id,
                player_a_name=detail.player_a_name,
                player_b_external_id=player_b_id,
                player_b_name=detail.player_b_name,
                source=fixture_source,
            )

            result = CanonicalMatchResult(
                match_external_id=match_external_id,
                player_a_external_id=player_a_id,
                player_b_external_id=player_b_id,
                winner_external_id=winner_id,
                player_a_legs=detail.player_a_legs,
                player_b_legs=detail.player_b_legs,
                completed_at=detail.played_at,
                source=result_source,
            )

            stats_a = self._statistics_record(
                match_id=match_id,
                match_external_id=match_external_id,
                player_external_id=player_a_id,
                player_stats=detail.player_a_stats,
                legs_won=detail.player_a_legs,
                legs_lost=detail.player_b_legs,
                retrieved_at=retrieved_at,
            )
            stats_b = self._statistics_record(
                match_id=match_id,
                match_external_id=match_external_id,
                player_external_id=player_b_id,
                player_stats=detail.player_b_stats,
                legs_won=detail.player_b_legs,
                legs_lost=detail.player_a_legs,
                retrieved_at=retrieved_at,
            )

            fixtures.append(fixture)
            results.append(result)
            statistics.extend([stats_a, stats_b])

        csv_by_type = {
            "fixtures": _models_to_csv("fixtures", fixtures),
            "results": _models_to_csv("results", results),
            "statistics": _models_to_csv("statistics", statistics),
        }
        filenames = {
            "fixtures": "modus_fixtures.csv",
            "results": "modus_results.csv",
            "statistics": "modus_statistics.csv",
        }

        return ModusCanonicalBuild(
            manifest=manifest,
            fixtures=fixtures,
            results=results,
            statistics=statistics,
            csv_by_type=csv_by_type,
            filenames=filenames,
        )

    @staticmethod
    def _statistics_record(
        *,
        match_id: int,
        match_external_id: str,
        player_external_id: str,
        player_stats,
        legs_won: int,
        legs_lost: int,
        retrieved_at: datetime,
    ) -> CanonicalPlayerMatchStatistics:
        source = SourceReference(
            provider=PROVIDER,
            external_id=modus_source_external_id(
                "statistics",
                match_id=match_id,
                player_external_id=player_external_id,
            ),
            retrieved_at=retrieved_at,
            competition_code=CompetitionCode.MODUS,
            confidence=RecordConfidence.VERIFIED,
        )
        return CanonicalPlayerMatchStatistics(
            match_external_id=match_external_id,
            player_external_id=player_external_id,
            three_dart_average=player_stats.three_dart_average,
            scores_100_plus=player_stats.scores_100_plus,
            scores_140_plus=player_stats.scores_140_plus,
            scores_180=player_stats.scores_180,
            checkout_attempts=player_stats.checkout_attempts,
            checkouts_completed=player_stats.checkouts_completed,
            checkout_percentage=player_stats.checkout_percentage,
            highest_checkout=player_stats.highest_checkout,
            legs_won=legs_won,
            legs_lost=legs_lost,
            source=source,
        )


def _models_to_csv(entity_type: str, models: list) -> str:
    headers = list(allowed_headers(entity_type))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()

    for model in models:
        data = model.model_dump(mode="json")
        source = data.pop("source")
        row = {header: "" for header in headers}

        for key, value in data.items():
            if key in row and value is not None:
                row[key] = value

        source_values = {
            "source_provider": source["provider"],
            "source_external_id": source["external_id"],
            "source_retrieved_at": source["retrieved_at"],
            "source_competition_code": (
                source.get("competition_code") or ""
            ),
            "source_confidence": source["confidence"],
        }
        row.update(source_values)
        writer.writerow(row)

    return output.getvalue()
