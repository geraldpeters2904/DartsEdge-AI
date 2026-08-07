from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.collector.commit_bridge import (
    CollectorCommitBridge,
    CollectorCommitReport,
)
from app.collector.folder_preview import CollectorFolderPreview
from app.models.historical_import import HistoricalImportPreview
from app.services.collector_preview_service import (
    CollectorPreviewService,
)
from app.services.import_wizard_service import (
    ImportWizardService,
)


SUPPORTED_FILENAMES = {
    "fixtures": "fixtures.csv",
    "results": "results.csv",
    "statistics": "statistics.csv",
    "odds": "odds.csv",
}


@dataclass(frozen=True)
class AutomaticModusFolderImportResult:
    folder: Path
    preview_uuid: str
    batch_id: int
    batch_uuid: str
    created_matches: int
    created_players: int
    duplicate_matches: int
    rejected_rows: int
    entity_counts: Dict[str, int]

    @property
    def successful(self) -> bool:
        return self.rejected_rows == 0


class AutomaticModusFolderImportService:
    """
    Import one validated MODUS folder through the standard Collector path.

    The service builds canonical CSV in memory, persists a normal Collector
    preview, rebuilds and validates that preview, commits through the existing
    CollectorCommitBridge, and marks the preview as committed.
    """

    def __init__(
        self,
        *,
        wizard_service: Optional[
            ImportWizardService
        ] = None,
        preview_service: Optional[
            CollectorPreviewService
        ] = None,
        commit_bridge: Optional[
            CollectorCommitBridge
        ] = None,
    ) -> None:
        self.wizard_service = (
            wizard_service or ImportWizardService()
        )
        self.preview_service = (
            preview_service or CollectorPreviewService()
        )
        self.commit_bridge = (
            commit_bridge or CollectorCommitBridge()
        )

    def import_folder(
        self,
        db: Session,
        *,
        folder: str | Path,
    ) -> AutomaticModusFolderImportResult:
        folder_path = Path(folder).expanduser().resolve()

        payload = self.wizard_service.build_preview_payload(
            "modus-official",
            str(folder_path),
            allow_partial=False,
        )

        preview = self.preview_service.create_preview(
            db=db,
            provider=payload["provider"],
            competition=payload["competition"],
            csv_by_type=payload["csv_by_type"],
            filenames=payload["filenames"],
        )

        try:
            commit_preview = self._rebuild_commit_preview(
                db=db,
                preview=preview,
            )

            report = self.commit_bridge.commit(
                db=db,
                preview=commit_preview,
                filename=preview.filename,
            )

            self._mark_preview_committed(
                db=db,
                preview=preview,
                report=report,
            )

            return AutomaticModusFolderImportResult(
                folder=folder_path,
                preview_uuid=preview.preview_uuid,
                batch_id=report.batch_id,
                batch_uuid=report.batch_uuid,
                created_matches=report.created_matches,
                created_players=report.created_players,
                duplicate_matches=report.duplicate_matches,
                rejected_rows=report.rejected_rows,
                entity_counts=dict(report.entity_counts),
            )

        except Exception:
            db.rollback()
            raise

    def _rebuild_commit_preview(
        self,
        *,
        db: Session,
        preview: HistoricalImportPreview,
    ) -> CollectorFolderPreview:
        preview, mappings, session = (
            self.preview_service.rebuild(
                db=db,
                preview_uuid=preview.preview_uuid,
            )
        )

        if not session.ready_to_commit:
            raise ValueError(
                "The automatic MODUS preview is not ready to commit."
            )

        invalid_entities = [
            entity_type
            for entity_type, mapping in mappings.items()
            if not mapping.valid
        ]

        if invalid_entities:
            raise ValueError(
                "Invalid files remain in the automatic preview: "
                + ", ".join(sorted(invalid_entities))
                + "."
            )

        storage_payload = json.loads(preview.rows_json)
        filenames = storage_payload.get("filenames", {})

        discovered_files = {
            entity_type: Path(
                filenames.get(
                    entity_type,
                    SUPPORTED_FILENAMES[entity_type],
                )
            )
            for entity_type in mappings
        }

        supplied_filenames = {
            path.name
            for path in discovered_files.values()
        }

        missing_files = [
            filename
            for filename in SUPPORTED_FILENAMES.values()
            if filename not in supplied_filenames
        ]

        return CollectorFolderPreview(
            folder=Path("collector-previews")
            / preview.preview_uuid,
            provider=preview.provider,
            discovered_files=discovered_files,
            mappings=mappings,
            session=session,
            missing_files=missing_files,
        )

    @staticmethod
    def _mark_preview_committed(
        *,
        db: Session,
        preview: HistoricalImportPreview,
        report: CollectorCommitReport,
    ) -> None:
        preview.status = "committed"
        preview.batch_id = report.batch_id
        preview.committed_at = datetime.utcnow()

        db.commit()
        db.refresh(preview)
