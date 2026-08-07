from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.models.canonical_data import ProviderEntityMapping
from app.services.modus_folder_service import (
    ModusFolderImportService,
    ModusFolderManifest,
)


@dataclass(frozen=True)
class HistoricalImportFolder:
    folder: Path
    manifest: Optional[ModusFolderManifest]
    status: str
    imported_count: int
    error_message: Optional[str] = None

    @property
    def expected_count(self) -> int:
        return (
            len(self.manifest.expected_match_ids)
            if self.manifest is not None
            else 0
        )

    @property
    def validated_count(self) -> int:
        return (
            len(self.manifest.validated_match_ids)
            if self.manifest is not None
            else 0
        )

    @property
    def missing_count(self) -> int:
        return (
            len(self.manifest.missing_match_ids)
            if self.manifest is not None
            else 0
        )

    @property
    def series_label(self) -> str:
        return (
            self.manifest.series_label
            if self.manifest and self.manifest.series_label
            else "—"
        )

    @property
    def week_label(self) -> str:
        return (
            self.manifest.week_label
            if self.manifest and self.manifest.week_label
            else "—"
        )

    @property
    def group(self) -> str:
        return (
            self.manifest.group
            if self.manifest and self.manifest.group
            else "—"
        )

    @property
    def import_url(self) -> str:
        return (
            "/admin/collector/import?source_path="
            + quote(str(self.folder))
        )


@dataclass(frozen=True)
class HistoricalImportLibrary:
    root: Path
    folders: List[HistoricalImportFolder]

    @property
    def discovered_count(self) -> int:
        return len(self.folders)

    @property
    def ready_count(self) -> int:
        return sum(1 for item in self.folders if item.status == "ready")

    @property
    def incomplete_count(self) -> int:
        return sum(1 for item in self.folders if item.status == "incomplete")

    @property
    def imported_count(self) -> int:
        return sum(1 for item in self.folders if item.status == "imported")

    @property
    def partially_imported_count(self) -> int:
        return sum(
            1 for item in self.folders
            if item.status == "partially_imported"
        )

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.folders if item.status == "error")


class HistoricalImportManagerService:
    """
    Discover historical MODUS group folders and compare them with warehouse
    provider mappings. This service is read-only.
    """

    def __init__(self):
        self.folder_service = ModusFolderImportService()

    def scan(
        self,
        db: Session,
        root: str | Path,
    ) -> HistoricalImportLibrary:
        root_path = Path(root).expanduser().resolve()

        if not root_path.exists():
            raise ValueError(
                f"Historical import root does not exist: {root_path}"
            )
        if not root_path.is_dir():
            raise ValueError(
                f"Historical import root is not a folder: {root_path}"
            )

        folders = []
        for results_file in sorted(
            root_path.rglob("results.html"),
            key=lambda path: str(path).casefold(),
        ):
            folders.append(
                self._inspect_folder(db, results_file.parent)
            )

        return HistoricalImportLibrary(
            root=root_path,
            folders=folders,
        )

    def _inspect_folder(
        self,
        db: Session,
        folder: Path,
    ) -> HistoricalImportFolder:
        try:
            manifest = self.folder_service.inspect(folder)
            importable_match_ids = self._importable_match_ids(
                manifest
            )
            imported_count = self._imported_fixture_count(
                db,
                importable_match_ids,
            )
            status = self._status(
                manifest,
                imported_count,
                importable_count=len(importable_match_ids),
            )

            return HistoricalImportFolder(
                folder=folder,
                manifest=manifest,
                status=status,
                imported_count=imported_count,
            )
        except Exception as exc:
            return HistoricalImportFolder(
                folder=folder,
                manifest=None,
                status="error",
                imported_count=0,
                error_message=str(exc),
            )

    def _importable_match_ids(
        self,
        manifest: ModusFolderManifest,
    ) -> List[int]:
        if manifest.results_file is None:
            return list(manifest.expected_match_ids)

        page = self.folder_service.results_parser.parse_results_document(
            manifest.results_file.read_text(encoding="utf-8")
        )

        return [
            match.match_id
            for match in page.matches
            if not (
                match.player_a_legs == 0
                and match.player_b_legs == 0
            )
        ]

    @staticmethod
    def _imported_fixture_count(
        db: Session,
        match_ids: List[int],
    ) -> int:
        if not match_ids:
            return 0

        external_ids = [
            f"modus-match-{match_id}"
            for match_id in match_ids
        ]

        return (
            db.query(ProviderEntityMapping)
            .filter(
                ProviderEntityMapping.provider == "modus-official",
                ProviderEntityMapping.entity_type == "fixture",
                ProviderEntityMapping.external_id.in_(external_ids),
            )
            .count()
        )

    @staticmethod
    def _status(
        manifest: ModusFolderManifest,
        imported_count: int,
        *,
        importable_count: Optional[int] = None,
    ) -> str:
        target_count = (
            len(manifest.expected_match_ids)
            if importable_count is None
            else int(importable_count)
        )

        if manifest.ready and imported_count >= target_count:
            return "imported"

        if imported_count > 0:
            return "partially_imported"

        if manifest.ready:
            return "ready"

        if manifest.results_file is not None:
            return "incomplete"

        return "error"
