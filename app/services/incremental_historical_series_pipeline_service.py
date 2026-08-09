from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.services.automatic_modus_folder_import_service import (
    AutomaticModusFolderImportService,
)
from app.services.capture_executor_service import (
    CaptureExecutorService,
)
from app.services.historical_capture_config import (
    HistoricalCaptureConfigService,
)
from app.services.historical_import_manager_service import (
    HistoricalImportManagerService,
)
from app.services.modus_capture_session_service import (
    ModusCaptureSessionService,
)
from app.services.modus_historical_series_preparation_service import (
    ModusHistoricalSeriesPreparationService,
)


@dataclass(frozen=True)
class IncrementalHistoricalSeriesPipelineResult:
    root: Path
    action: str
    message: str
    continue_running: bool
    current_folder: Optional[Path] = None
    current_match_id: Optional[int] = None
    import_report: Optional[object] = None
    preparation: Optional[object] = None
    error: Optional[str] = None

    @property
    def complete(self) -> bool:
        return self.action == "complete"

    @property
    def blocked(self) -> bool:
        return self.action in {
            "blocked",
            "failed",
            "error",
        }


class IncrementalHistoricalSeriesPipelineService:
    """
    Capture, validate and import one historical MODUS group incrementally.

    Only folders belonging to the selected series are inspected. Future
    incomplete folders do not block a ready group from being imported.
    """

    def __init__(
        self,
        *,
        import_manager: Optional[
            HistoricalImportManagerService
        ] = None,
        preparation_service: Optional[
            ModusHistoricalSeriesPreparationService
        ] = None,
        capture_session_service: Optional[
            ModusCaptureSessionService
        ] = None,
        capture_executor: Optional[
            CaptureExecutorService
        ] = None,
        capture_config_service: Optional[
            HistoricalCaptureConfigService
        ] = None,
        folder_import_service: Optional[
            AutomaticModusFolderImportService
        ] = None,
    ) -> None:
        self.import_manager = (
            import_manager or HistoricalImportManagerService()
        )
        self.preparation_service = (
            preparation_service
            or ModusHistoricalSeriesPreparationService()
        )
        self.capture_session_service = (
            capture_session_service
            or ModusCaptureSessionService()
        )
        self.capture_executor = (
            capture_executor or CaptureExecutorService()
        )
        self.capture_config_service = (
            capture_config_service
            or HistoricalCaptureConfigService()
        )
        self.folder_import_service = (
            folder_import_service
            or AutomaticModusFolderImportService()
        )

    def run_cycle(
        self,
        db: Session,
        *,
        root: str | Path,
        catalog_html: str,
        watch_folder: str = "~/Downloads",
    ) -> IncrementalHistoricalSeriesPipelineResult:
        del watch_folder  # Direct capture no longer depends on Downloads.

        root_path = Path(root).expanduser().resolve()

        try:
            preparation = self.preparation_service.run_cycle(
                root=root_path,
                catalog_html=catalog_html,
            )

            series_id = self._selected_series_id(
                preparation
            )
            series_root = root_path / f"Series_{series_id}"
            library = self.import_manager.scan(
                db,
                series_root,
            )

            ready = next(
                (
                    item
                    for item in library.folders
                    if item.status == "ready"
                ),
                None,
            )

            if ready is not None:
                report = self.folder_import_service.import_folder(
                    db,
                    folder=ready.folder,
                )

                if not getattr(report, "successful", False):
                    return IncrementalHistoricalSeriesPipelineResult(
                        root=root_path,
                        action="blocked",
                        message=(
                            f"Import failed for {ready.folder}."
                        ),
                        continue_running=False,
                        current_folder=ready.folder,
                        import_report=report,
                        preparation=preparation,
                        error=getattr(
                            report,
                            "error_message",
                            None,
                        ),
                    )

                return IncrementalHistoricalSeriesPipelineResult(
                    root=root_path,
                    action="imported",
                    message=(
                        f"Imported {ready.manifest.series_label} · "
                        f"{ready.manifest.week_label} · "
                        f"{ready.manifest.group}."
                    ),
                    continue_running=True,
                    current_folder=ready.folder,
                    import_report=report,
                    preparation=preparation,
                )

            invalid = next(
                (
                    item
                    for item in library.folders
                    if item.status == "error"
                ),
                None,
            )

            if invalid is not None:
                return IncrementalHistoricalSeriesPipelineResult(
                    root=root_path,
                    action="blocked",
                    message=(
                        "A historical folder requires review before "
                        "the series can continue."
                    ),
                    continue_running=False,
                    current_folder=invalid.folder,
                    preparation=preparation,
                    error=invalid.error_message,
                )

            incomplete = next(
                (
                    item
                    for item in library.folders
                    if item.status in {
                        "incomplete",
                        "partially_imported",
                    }
                ),
                None,
            )

            if incomplete is not None:
                request = (
                    self.capture_session_service
                    .next_capture_request(
                        incomplete.folder
                    )
                )

                if request is None:
                    manifest = incomplete.manifest

                    if manifest is not None and manifest.ready:
                        report = (
                            self.folder_import_service.import_folder(
                                db,
                                folder=incomplete.folder,
                            )
                        )

                        if not getattr(
                            report,
                            "successful",
                            False,
                        ):
                            return (
                                IncrementalHistoricalSeriesPipelineResult(
                                    root=root_path,
                                    action="blocked",
                                    message=(
                                        "Import failed for "
                                        f"{incomplete.folder}."
                                    ),
                                    continue_running=False,
                                    current_folder=incomplete.folder,
                                    import_report=report,
                                    preparation=preparation,
                                    error=getattr(
                                        report,
                                        "error_message",
                                        None,
                                    ),
                                )
                            )

                        return IncrementalHistoricalSeriesPipelineResult(
                            root=root_path,
                            action="imported",
                            message=(
                                f"Imported "
                                f"{manifest.series_label} · "
                                f"{manifest.week_label} · "
                                f"{manifest.group}."
                            ),
                            continue_running=True,
                            current_folder=incomplete.folder,
                            import_report=report,
                            preparation=preparation,
                        )

                    return IncrementalHistoricalSeriesPipelineResult(
                        root=root_path,
                        action="blocked",
                        message=(
                            "The incomplete folder has no pending "
                            "capture request."
                        ),
                        continue_running=False,
                        current_folder=incomplete.folder,
                        preparation=preparation,
                    )

                config = self.capture_config_service.load(
                    root_path
                )
                capture = self.capture_executor.execute(
                    request,
                    provider_name=config.provider,
                )

                destination_folder = getattr(
                    request,
                    "destination_folder",
                    None,
                )
                destination_filename = getattr(
                    request,
                    "destination_filename",
                    None,
                )

                if (
                    destination_folder is not None
                    and destination_filename
                ):
                    expected_path = (
                        destination_folder
                        / destination_filename
                    )

                    if (
                        not getattr(
                            capture,
                            "successful",
                            True,
                        )
                        or not expected_path.is_file()
                    ):
                        return IncrementalHistoricalSeriesPipelineResult(
                            root=root_path,
                            action=(
                                "waiting"
                                if getattr(
                                    capture,
                                    "waiting",
                                    False,
                                )
                                else "error"
                            ),
                            message=(
                                getattr(
                                    capture,
                                    "message",
                                    None,
                                )
                                or (
                                    "Capture did not produce the expected "
                                    f"file for match {request.match_id}."
                                )
                            ),
                            continue_running=False,
                            current_folder=incomplete.folder,
                            current_match_id=request.match_id,
                            preparation=preparation,
                            error=(
                                getattr(
                                    capture,
                                    "error",
                                    None,
                                )
                                or (
                                    "Expected capture file was not written: "
                                    f"{expected_path}"
                                )
                            ),
                        )

                refreshed = (
                    self.capture_session_service
                    .refresh_session(
                        incomplete.folder
                    )
                )

                next_item = getattr(
                    refreshed,
                    "next_item",
                    None,
                )

                if (
                    next_item is not None
                    and getattr(
                        next_item,
                        "match_id",
                        None,
                    )
                    == request.match_id
                ):
                    return IncrementalHistoricalSeriesPipelineResult(
                        root=root_path,
                        action="error",
                        message=(
                            f"Capture for match {request.match_id} "
                            "was not accepted by the capture session."
                        ),
                        continue_running=False,
                        current_folder=incomplete.folder,
                        current_match_id=request.match_id,
                        preparation=preparation,
                        error=(
                            "The saved file is missing, unreadable or "
                            "recognised as a browser error page."
                        ),
                    )

                return IncrementalHistoricalSeriesPipelineResult(
                    root=root_path,
                    action="captured",
                    message=(
                        f"Captured match {request.match_id} for "
                        f"{refreshed.series_label} · "
                        f"{refreshed.week_label} · "
                        f"{refreshed.group}."
                    ),
                    continue_running=True,
                    current_folder=incomplete.folder,
                    current_match_id=request.match_id,
                    preparation=preparation,
                )

            if preparation.prepared:
                return IncrementalHistoricalSeriesPipelineResult(
                    root=root_path,
                    action="prepared",
                    message=preparation.message,
                    continue_running=True,
                    current_folder=(
                        preparation.navigation_result
                        .destination_folder
                        if preparation.navigation_result
                        else None
                    ),
                    preparation=preparation,
                )

            if preparation.complete:
                return IncrementalHistoricalSeriesPipelineResult(
                    root=root_path,
                    action="complete",
                    message=(
                        "The selected MODUS series is fully "
                        "captured and imported."
                    ),
                    continue_running=False,
                    preparation=preparation,
                )

            return IncrementalHistoricalSeriesPipelineResult(
                root=root_path,
                action="waiting",
                message=preparation.message,
                continue_running=True,
                preparation=preparation,
            )

        except Exception as exc:
            rollback = getattr(db, "rollback", None)

            if callable(rollback):
                rollback()

            return IncrementalHistoricalSeriesPipelineResult(
                root=root_path,
                action="error",
                message=(
                    "Incremental historical series pipeline failed."
                ),
                continue_running=False,
                error=str(exc),
            )

    @staticmethod
    def _selected_series_id(
        preparation,
    ) -> int:
        target = getattr(
            preparation,
            "current_target",
            None,
        )

        if target is not None:
            return int(target.series_id)

        navigation = getattr(
            preparation,
            "navigation_result",
            None,
        )

        if navigation is not None:
            return int(navigation.target.series_id)

        batch = getattr(preparation, "batch", None)
        items = getattr(batch, "items", None) or ()

        if items:
            return int(items[0].series_id)

        raise ValueError(
            "Unable to determine the selected MODUS series."
        )
