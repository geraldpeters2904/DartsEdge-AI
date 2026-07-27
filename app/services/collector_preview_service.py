from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Dict, Mapping, Optional

from app.collector.canonical_mapper import CanonicalCsvMapper
from app.models.historical_import import HistoricalImportPreview


SUPPORTED_ENTITY_TYPES = (
    "fixtures",
    "results",
    "statistics",
    "odds",
)


class CollectorPreviewService:
    """Persist and reconstruct combined canonical CSV previews."""

    def __init__(self):
        self.mapper = CanonicalCsvMapper()

    def create_preview(
        self,
        *,
        db,
        provider: str,
        competition: str,
        csv_by_type: Mapping[str, str],
        filenames: Optional[Mapping[str, str]] = None,
    ) -> HistoricalImportPreview:
        provider = provider.strip()
        competition = competition.strip().upper()

        if not provider:
            raise ValueError("Provider must not be blank.")

        if not competition:
            raise ValueError("Competition must not be blank.")

        filtered_csv = {
            entity_type: csv_text
            for entity_type, csv_text in csv_by_type.items()
            if (
                entity_type in SUPPORTED_ENTITY_TYPES
                and csv_text.strip()
            )
        }

        if not filtered_csv:
            raise ValueError(
                "Select at least one canonical CSV file."
            )

        mappings, session = self.mapper.preview_texts(
            provider=provider,
            csv_by_type=filtered_csv,
        )

        file_report: Dict[str, dict] = {}

        for entity_type in SUPPORTED_ENTITY_TYPES:
            mapping = mappings.get(entity_type)

            if mapping is None:
                file_report[entity_type] = {
                    "present": False,
                    "filename": None,
                    "valid": False,
                    "received": 0,
                    "mapped": 0,
                    "errors": 0,
                    "issues": [],
                }
                continue

            summary = session.entity_summaries.get(
                entity_type
            )

            file_report[entity_type] = {
                "present": True,
                "filename": (
                    filenames.get(entity_type)
                    if filenames
                    else f"{entity_type}.csv"
                ),
                "valid": mapping.valid,
                "received": (
                    summary.received
                    if summary is not None
                    else len(mapping.parse_result.records)
                ),
                "mapped": len(mapping.records),
                "errors": mapping.error_count,
                "issues": [
                    {
                        "severity": issue.severity,
                        "code": issue.code,
                        "message": issue.message,
                        "row_number": issue.row_number,
                    }
                    for issue in mapping.issues
                ],
            }

        report = {
            "provider": provider,
            "competition": competition,
            "ready_to_commit": (
                bool(filtered_csv)
                and all(
                    mapping.valid
                    for mapping in mappings.values()
                )
                and session.ready_to_commit
            ),
            "quality_score": session.quality_score,
            "totals": session.to_dict()["totals"],
            "entities": session.to_dict()["entities"],
            "issues": session.to_dict()["issues"],
            "files": file_report,
        }

        storage_payload = {
            "csv_by_type": filtered_csv,
            "filenames": dict(filenames or {}),
        }

        display_filename = ", ".join(
            file_report[entity_type]["filename"]
            for entity_type in SUPPORTED_ENTITY_TYPES
            if file_report[entity_type]["present"]
        )

        preview = HistoricalImportPreview(
            preview_uuid=str(uuid.uuid4()),
            filename=display_filename or "collector-preview",
            provider=provider,
            competition_code=competition,
            status="pending",
            rows_json=json.dumps(
                storage_payload,
                separators=(",", ":"),
            ),
            report_json=json.dumps(
                report,
                separators=(",", ":"),
            ),
            created_at=datetime.utcnow(),
        )

        db.add(preview)
        db.commit()
        db.refresh(preview)

        return preview

    @staticmethod
    def get_preview(
        *,
        db,
        preview_uuid: str,
    ) -> Optional[HistoricalImportPreview]:
        return (
            db.query(HistoricalImportPreview)
            .filter_by(preview_uuid=preview_uuid)
            .first()
        )

    def preview_report(
        self,
        *,
        db,
        preview_uuid: str,
    ) -> dict:
        preview = self.get_preview(
            db=db,
            preview_uuid=preview_uuid,
        )

        if preview is None:
            raise ValueError(
                "Collector preview was not found."
            )

        return json.loads(preview.report_json)

    def rebuild(
        self,
        *,
        db,
        preview_uuid: str,
    ):
        preview = self.get_preview(
            db=db,
            preview_uuid=preview_uuid,
        )

        if preview is None:
            raise ValueError(
                "Collector preview was not found."
            )

        storage_payload = json.loads(preview.rows_json)

        mappings, session = self.mapper.preview_texts(
            provider=preview.provider,
            csv_by_type=storage_payload.get(
                "csv_by_type",
                {},
            ),
        )

        return preview, mappings, session

    def cancel_preview(
        self,
        *,
        db,
        preview_uuid: str,
    ) -> HistoricalImportPreview:
        preview = self.get_preview(
            db=db,
            preview_uuid=preview_uuid,
        )

        if preview is None:
            raise ValueError(
                "Collector preview was not found."
            )

        if preview.status == "committed":
            raise ValueError(
                "A committed preview cannot be cancelled."
            )

        preview.status = "cancelled"
        db.commit()
        db.refresh(preview)

        return preview
