from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from app.services.historical_capture_batch_service import (
    HistoricalCaptureBatch,
    HistoricalCaptureBatchService,
)
from app.services.modus_capture_session_service import (
    SESSION_FILENAME,
    ModusCaptureSession,
    ModusCaptureSessionService,
)
from app.services.modus_historical_catalog_service import (
    ModusHistoricalCaptureTarget,
    ModusHistoricalCatalogService,
)
from app.services.modus_historical_navigator_service import (
    ModusHistoricalNavigationResult,
    ModusHistoricalNavigatorService,
)


@dataclass(frozen=True)
class ModusHistoricalSeriesPreparationResult:
    root: Path
    action: str
    message: str
    continue_running: bool
    total_targets: int
    prepared_targets: int
    completed_targets: int
    remaining_targets: int
    current_target: Optional[
        ModusHistoricalCaptureTarget
    ] = None
    navigation_result: Optional[
        ModusHistoricalNavigationResult
    ] = None
    batch: Optional[HistoricalCaptureBatch] = None

    @property
    def prepared(self) -> bool:
        return self.action == "prepared"

    @property
    def capture_ready(self) -> bool:
        return self.action == "capture_ready"

    @property
    def complete(self) -> bool:
        return self.action == "complete"


class ModusHistoricalSeriesPreparationService:
    """
    Prepare one missing MODUS group per cycle for a selected series.

    Existing capture sessions are reused. Completed sessions are skipped.
    After each preparation cycle, the normal HistoricalCaptureBatch is
    rebuilt from every discovered results.html page so the established
    runner can resume across the entire selected series.
    """

    def __init__(
        self,
        *,
        catalog_service: Optional[
            ModusHistoricalCatalogService
        ] = None,
        navigator_service: Optional[
            ModusHistoricalNavigatorService
        ] = None,
        capture_session_service: Optional[
            ModusCaptureSessionService
        ] = None,
        batch_service: Optional[
            HistoricalCaptureBatchService
        ] = None,
    ) -> None:
        self.catalog_service = (
            catalog_service
            or ModusHistoricalCatalogService()
        )
        self.navigator_service = (
            navigator_service
            or ModusHistoricalNavigatorService()
        )
        self.capture_session_service = (
            capture_session_service
            or ModusCaptureSessionService()
        )
        self.batch_service = (
            batch_service
            or HistoricalCaptureBatchService()
        )

    def run_cycle(
        self,
        *,
        root: str | Path,
        catalog_html: str,
    ) -> ModusHistoricalSeriesPreparationResult:
        root_path = Path(root).expanduser().resolve()
        targets = (
            self.catalog_service
            .targets_for_selected_series(catalog_html)
        )

        if not targets:
            raise ValueError(
                "The selected MODUS series has no capture targets."
            )

        prepared: List[
            Tuple[
                ModusHistoricalCaptureTarget,
                ModusCaptureSession,
            ]
        ] = []
        completed_count = 0
        first_incomplete = None

        for target in targets:
            destination = (
                self.navigator_service.destination_folder(
                    root=root_path,
                    target=target,
                )
            )
            session_path = destination / SESSION_FILENAME

            if not session_path.is_file():
                navigation = (
                    self.navigator_service.prepare_target(
                        root=root_path,
                        target=target,
                    )
                )

                prepared.append(
                    (target, navigation.session)
                )

                batch = self._rebuild_batch(
                    root=root_path,
                    targets=targets,
                )

                return (
                    ModusHistoricalSeriesPreparationResult(
                        root=root_path,
                        action="prepared",
                        message=(
                            f"Prepared {target.series_label} · "
                            f"{target.week_label} · "
                            f"{target.group}. "
                            "The capture batch was refreshed."
                        ),
                        continue_running=True,
                        total_targets=len(targets),
                        prepared_targets=(
                            self._prepared_count(
                                root_path,
                                targets,
                            )
                        ),
                        completed_targets=(
                            self._completed_count(
                                root_path,
                                targets,
                            )
                        ),
                        remaining_targets=(
                            self._remaining_count(
                                root_path,
                                targets,
                            )
                        ),
                        current_target=target,
                        navigation_result=navigation,
                        batch=batch,
                    )
                )

            session = (
                self.capture_session_service.load_session(
                    destination
                )
            )
            prepared.append((target, session))

            if session.complete:
                completed_count += 1
            elif first_incomplete is None:
                first_incomplete = target

        batch = self._rebuild_batch(
            root=root_path,
            targets=targets,
        )

        if first_incomplete is not None:
            return ModusHistoricalSeriesPreparationResult(
                root=root_path,
                action="capture_ready",
                message=(
                    f"{first_incomplete.series_label} · "
                    f"{first_incomplete.week_label} · "
                    f"{first_incomplete.group} is ready for "
                    "match-page capture."
                ),
                continue_running=True,
                total_targets=len(targets),
                prepared_targets=len(prepared),
                completed_targets=completed_count,
                remaining_targets=(
                    len(targets) - completed_count
                ),
                current_target=first_incomplete,
                batch=batch,
            )

        return ModusHistoricalSeriesPreparationResult(
            root=root_path,
            action="complete",
            message=(
                "Every historical target in the selected "
                "MODUS series has a complete capture session."
            ),
            continue_running=False,
            total_targets=len(targets),
            prepared_targets=len(prepared),
            completed_targets=completed_count,
            remaining_targets=0,
            batch=batch,
        )

    def _rebuild_batch(
        self,
        *,
        root: Path,
        targets: Tuple[
            ModusHistoricalCaptureTarget,
            ...,
        ],
    ) -> HistoricalCaptureBatch:
        results_pages = []

        for target in targets:
            destination = (
                self.navigator_service.destination_folder(
                    root=root,
                    target=target,
                )
            )
            session_path = destination / SESSION_FILENAME
            results_path = destination / "results.html"

            if (
                session_path.is_file()
                and results_path.is_file()
            ):
                results_pages.append(
                    (
                        self._results_filename(target),
                        results_path.read_text(
                            encoding="utf-8"
                        ),
                    )
                )

        if not results_pages:
            raise ValueError(
                "No prepared MODUS results pages are available "
                "for the historical capture batch."
            )

        return self.batch_service.create(
            root=root,
            results_pages=results_pages,
        )

    def _prepared_count(
        self,
        root: Path,
        targets: Tuple[
            ModusHistoricalCaptureTarget,
            ...,
        ],
    ) -> int:
        return sum(
            1
            for target in targets
            if (
                self.navigator_service.destination_folder(
                    root=root,
                    target=target,
                )
                / SESSION_FILENAME
            ).is_file()
        )

    def _completed_count(
        self,
        root: Path,
        targets: Tuple[
            ModusHistoricalCaptureTarget,
            ...,
        ],
    ) -> int:
        count = 0

        for target in targets:
            destination = (
                self.navigator_service.destination_folder(
                    root=root,
                    target=target,
                )
            )

            if not (
                destination / SESSION_FILENAME
            ).is_file():
                continue

            session = (
                self.capture_session_service.load_session(
                    destination
                )
            )

            if session.complete:
                count += 1

        return count

    def _remaining_count(
        self,
        root: Path,
        targets: Tuple[
            ModusHistoricalCaptureTarget,
            ...,
        ],
    ) -> int:
        return (
            len(targets)
            - self._completed_count(root, targets)
        )

    @staticmethod
    def _results_filename(
        target: ModusHistoricalCaptureTarget,
    ) -> str:
        return (
            f"series_{target.series_id}_"
            f"week_{target.week_id}_"
            f"{target.group.replace(' ', '_').casefold()}"
            ".html"
        )
