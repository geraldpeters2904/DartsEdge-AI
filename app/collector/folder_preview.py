from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from app.collector.canonical_mapper import (
    CanonicalCsvMapper,
    CanonicalCsvMappingResult,
)
from app.services.import_session_service import ImportSessionResult


SUPPORTED_FILES = {
    "fixtures": "fixtures.csv",
    "results": "results.csv",
    "statistics": "statistics.csv",
    "odds": "odds.csv",
}


@dataclass
class CollectorFolderPreview:
    folder: Path
    provider: str
    discovered_files: Dict[str, Path]
    mappings: Dict[str, CanonicalCsvMappingResult]
    session: ImportSessionResult
    missing_files: List[str]

    @property
    def mapping_error_count(self) -> int:
        return sum(
            mapping.error_count
            for mapping in self.mappings.values()
        )

    @property
    def ready_to_commit(self) -> bool:
        return (
            bool(self.discovered_files)
            and self.mapping_error_count == 0
            and self.session.ready_to_commit
        )

    def to_dict(self):
        return {
            "folder": str(self.folder),
            "provider": self.provider,
            "ready_to_commit": self.ready_to_commit,
            "discovered_files": {
                entity_type: str(path)
                for entity_type, path in self.discovered_files.items()
            },
            "missing_files": self.missing_files,
            "mapping_errors": self.mapping_error_count,
            "quality_score": self.session.quality_score,
            "totals": {
                "received": self.session.total_received,
                "valid": self.session.total_valid,
                "rejected": self.session.total_rejected,
                "duplicates": self.session.total_duplicates,
                "errors": self.session.error_count,
                "warnings": self.session.warning_count,
            },
        }


class CollectorFolderPreviewService:
    """Preview canonical CSV files found in one directory."""

    def __init__(self):
        self.mapper = CanonicalCsvMapper()

    def preview(
        self,
        *,
        folder: Path,
        provider: str,
    ) -> CollectorFolderPreview:
        folder = Path(folder)

        if not folder.exists():
            raise FileNotFoundError(folder)

        if not folder.is_dir():
            raise NotADirectoryError(folder)

        provider = provider.strip()

        if not provider:
            raise ValueError("provider must not be blank")

        discovered_files: Dict[str, Path] = {}
        csv_by_type: Dict[str, str] = {}

        for entity_type, filename in SUPPORTED_FILES.items():
            path = folder / filename

            if path.is_file():
                discovered_files[entity_type] = path
                csv_by_type[entity_type] = path.read_text(
                    encoding="utf-8-sig"
                )

        missing_files = [
            filename
            for entity_type, filename in SUPPORTED_FILES.items()
            if entity_type not in discovered_files
        ]

        mappings, session = self.mapper.preview_texts(
            provider=provider,
            csv_by_type=csv_by_type,
        )

        return CollectorFolderPreview(
            folder=folder,
            provider=provider,
            discovered_files=discovered_files,
            mappings=mappings,
            session=session,
            missing_files=missing_files,
        )
