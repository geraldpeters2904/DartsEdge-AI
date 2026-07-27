from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from app.collector.folder_preview import CollectorFolderPreview
from app.models.historical_import import HistoricalImportBatch
from app.schemas.canonical import CanonicalFixture
from app.services.historical_import_service import import_rows


@dataclass(frozen=True)
class CollectorCommitReport:
    """Summary of one collector commit operation."""

    batch: HistoricalImportBatch
    entity_counts: Dict[str, int]

    @property
    def batch_id(self) -> int:
        return self.batch.id

    @property
    def batch_uuid(self) -> str:
        return self.batch.batch_uuid

    @property
    def created_matches(self) -> int:
        return self.batch.created_matches

    @property
    def created_players(self) -> int:
        return self.batch.created_players

    @property
    def duplicate_matches(self) -> int:
        return self.batch.duplicate_matches

    @property
    def rejected_rows(self) -> int:
        return self.batch.rejected_rows


class CollectorCommitBridge:
    """
    Commit validated collector records through the existing historical importer.

    This first version supports fixtures only. Results, statistics and odds
    will be added in separate commits.
    """

    SUPPORTED_ENTITY_TYPES = {"fixtures"}

    def commit(
        self,
        *,
        db,
        preview: CollectorFolderPreview,
        filename: str | None = None,
    ) -> CollectorCommitReport:
        self._validate_preview(preview)

        fixture_mapping = preview.mappings.get("fixtures")
        fixtures = list(fixture_mapping.records if fixture_mapping else [])

        if not fixtures:
            raise ValueError(
                "The collector preview contains no fixture records to commit."
            )

        rows = [
            self._fixture_to_historical_row(fixture)
            for fixture in fixtures
        ]

        batch = import_rows(
            db,
            rows,
            filename=filename or self._default_filename(preview),
            provider=preview.provider,
            competition=self._competition_code(fixtures),
        )

        return CollectorCommitReport(
            batch=batch,
            entity_counts={
                "fixtures": len(fixtures),
                "results": 0,
                "statistics": 0,
                "odds": 0,
            },
        )

    def _validate_preview(
        self,
        preview: CollectorFolderPreview,
    ) -> None:
        if not isinstance(preview, CollectorFolderPreview):
            raise TypeError(
                "preview must be a CollectorFolderPreview instance."
            )

        if not preview.ready_to_commit:
            raise ValueError(
                "Collector preview is not ready to commit."
            )

        unsupported = (
            set(preview.mappings)
            - self.SUPPORTED_ENTITY_TYPES
        )

        if unsupported:
            names = ", ".join(sorted(unsupported))
            raise ValueError(
                "This commit-bridge version supports fixtures only. "
                f"Unsupported preview entities: {names}."
            )

    @staticmethod
    def _fixture_to_historical_row(
        fixture: CanonicalFixture,
    ) -> dict:
        return {
            "external_id": fixture.external_id,
            "date": fixture.scheduled_at.date(),
            "competition": fixture.competition_code.value,
            "tournament": fixture.competition_name,
            "stage": fixture.stage or "Scheduled",
            "match_format": fixture.match_format,
            "status": fixture.status.value,
            "player_a": fixture.player_a_name,
            "player_b": fixture.player_b_name,
            "winner": None,
            "score": None,
            "first_180_player": None,
            "first_leg_winner": None,
            "provider": fixture.source.provider,
            "player_a_stats": {
                "one80s": 0,
                "average": 0.0,
                "checkout": 0.0,
                "first9_average": 0.0,
                "highest_checkout": 0,
            },
            "player_b_stats": {
                "one80s": 0,
                "average": 0.0,
                "checkout": 0.0,
                "first9_average": 0.0,
                "highest_checkout": 0,
            },
        }

    @staticmethod
    def _competition_code(
        fixtures: List[CanonicalFixture],
    ) -> str:
        competition_codes = {
            fixture.competition_code.value
            for fixture in fixtures
        }

        if len(competition_codes) == 1:
            return next(iter(competition_codes))

        return "OTHER"

    @staticmethod
    def _default_filename(
        preview: CollectorFolderPreview,
    ) -> str:
        folder_name = Path(preview.folder).name or "collector"
        return f"{folder_name}-fixtures.csv"