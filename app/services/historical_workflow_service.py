from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.services.historical_runner_service import (
    HistoricalRunnerService,
    HistoricalRunnerState,
)
from app.services.modus_capture_assistant_runtime import (
    capture_assistant_service,
)
from app.services.modus_capture_assistant_service import (
    CaptureAssistantStatus,
    ModusCaptureAssistantService,
)


@dataclass(frozen=True)
class HistoricalWorkflowStatus:
    runner: HistoricalRunnerState
    assistant: CaptureAssistantStatus

    @property
    def status(self) -> str:
        return self.runner.status

    @property
    def running(self) -> bool:
        return self.runner.running

    @property
    def paused(self) -> bool:
        return self.runner.paused

    @property
    def stopped(self) -> bool:
        return self.runner.stopped

    @property
    def current_match_id(self) -> Optional[int]:
        return self.runner.current_match_id

    @property
    def current_destination_folder(self) -> Optional[str]:
        return self.runner.current_destination_folder


class HistoricalWorkflowService:
    """Coordinate runner state and the MODUS Capture Assistant."""

    def __init__(
        self,
        *,
        runner_service: Optional[HistoricalRunnerService] = None,
        assistant_service: Optional[
            ModusCaptureAssistantService
        ] = None,
    ) -> None:
        self.runner_service = (
            runner_service or HistoricalRunnerService()
        )
        self.assistant_service = (
            assistant_service or capture_assistant_service
        )

    def status(
        self,
        root: str | Path,
    ) -> HistoricalWorkflowStatus:
        return HistoricalWorkflowStatus(
            runner=self.runner_service.load(root),
            assistant=self.assistant_service.status(),
        )

    def start(
        self,
        root: str | Path,
        *,
        watch_folder: str = "~/Downloads",
    ) -> HistoricalWorkflowStatus:
        runner = self.runner_service.start(root)

        if runner.complete:
            self._stop_assistant_if_running()
            return self.status(root)

        self._start_assistant_for_runner(
            root,
            runner,
            watch_folder,
        )

        return self.status(root)

    def pause(
        self,
        root: str | Path,
    ) -> HistoricalWorkflowStatus:
        self.runner_service.pause(root)
        self._stop_assistant_if_running()
        return self.status(root)

    def resume(
        self,
        root: str | Path,
        *,
        watch_folder: str = "~/Downloads",
    ) -> HistoricalWorkflowStatus:
        runner = self.runner_service.resume(root)

        if runner.complete:
            self._stop_assistant_if_running()
            return self.status(root)

        self._start_assistant_for_runner(
            root,
            runner,
            watch_folder,
        )

        return self.status(root)

    def stop(
        self,
        root: str | Path,
    ) -> HistoricalWorkflowStatus:
        self.runner_service.stop(root)
        self._stop_assistant_if_running()
        return self.status(root)

    def synchronise(
        self,
        root: str | Path,
    ) -> HistoricalWorkflowStatus:
        """
        Keep the assistant aligned with the runner's current capture group.

        The runner load refreshes batch progress. If capture has advanced into
        another group, week or series, the assistant is restarted against the
        new destination while preserving its current watch folder.
        """
        runner = self.runner_service.load(root)
        assistant = self.assistant_service.status()

        if runner.complete:
            if assistant.running:
                self.assistant_service.stop()

            return self.status(root)

        if not runner.running:
            return self.status(root)

        destination = runner.current_destination_folder

        if not destination:
            error = "Historical runner has no current capture folder."
            self.runner_service.mark_failed(root, error)
            self._stop_assistant_if_running()
            raise ValueError(error)

        watch_folder = (
            assistant.watch_folder.strip()
            if assistant.watch_folder
            else "~/Downloads"
        )

        assistant_on_current_group = (
            assistant.running
            and self._same_folder(
                assistant.destination_folder,
                destination,
            )
        )

        if not assistant_on_current_group:
            try:
                self.assistant_service.start(
                    destination_folder=destination,
                    watch_folder=watch_folder,
                )
            except Exception as exc:
                self.runner_service.mark_failed(
                    root,
                    str(exc),
                )
                self._stop_assistant_if_running()
                raise

        return self.status(root)

    def _start_assistant_for_runner(
        self,
        root: str | Path,
        runner: HistoricalRunnerState,
        watch_folder: str,
    ) -> None:
        destination = runner.current_destination_folder

        if not destination:
            raise ValueError(
                "Historical runner has no current capture folder."
            )

        try:
            self.assistant_service.start(
                destination_folder=destination,
                watch_folder=watch_folder,
            )
        except Exception as exc:
            self.runner_service.mark_failed(root, str(exc))
            raise

    def _stop_assistant_if_running(self) -> None:
        if self.assistant_service.status().running:
            self.assistant_service.stop()

    @staticmethod
    def _same_folder(
        first: str,
        second: str,
    ) -> bool:
        if not first or not second:
            return False

        return (
            Path(first).expanduser().resolve()
            == Path(second).expanduser().resolve()
        )
