from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.services.capture_executor_service import (
    CaptureExecutorService,
)
from app.services.capture_iteration_history_service import (
    CaptureIterationHistoryService,
)
from app.services.capture_iteration_summary import (
    CaptureIterationSummary,
)
from app.services.historical_capture_config import (
    HistoricalCaptureConfigService,
)
from app.services.modus_capture_session_service import (
    ModusCaptureSessionService,
)
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
        capture_session_service: Optional[
            ModusCaptureSessionService
        ] = None,
        capture_executor: Optional[
            CaptureExecutorService
        ] = None,
        capture_config_service: Optional[
            HistoricalCaptureConfigService
        ] = None,
        capture_provider_name: Optional[str] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        history_service: Optional[
            CaptureIterationHistoryService
        ] = None,
        db_session_factory: Callable[[], Session] = SessionLocal,
    ) -> None:
        self.runner_service = (
            runner_service or HistoricalRunnerService()
        )
        self.assistant_service = (
            assistant_service or capture_assistant_service
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
        self.capture_provider_name = (
            capture_provider_name.strip().casefold()
            if capture_provider_name
            else None
        )
        self.sleep_fn = sleep_fn
        self.history_service = (
            history_service
            or CaptureIterationHistoryService()
        )
        self.db_session_factory = db_session_factory
        self.last_capture_summary: Optional[
            CaptureIterationSummary
        ] = None

    def latest_capture_summary(
        self,
    ) -> Optional[CaptureIterationSummary]:
        return self.last_capture_summary

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

    def capture_iteration(
        self,
        root: str | Path,
    ) -> HistoricalWorkflowStatus:
        """Execute one workflow iteration and record its summary."""
        started_at = datetime.now()
        matches_captured = 0
        bytes_written = 0
        captures_waiting = 0
        retries_attempted = 0
        provider_name = self.capture_provider_name
        match_id = None

        try:
            workflow = self.synchronise(root)
            match_id = workflow.current_match_id

            destination = workflow.current_destination_folder

            if workflow.running and destination:
                request = (
                    self.capture_session_service
                    .next_capture_request(destination)
                )

                if request is not None:
                    match_id = request.match_id
                    config = self.capture_config_service.load(
                        root
                    )
                    provider_name = (
                        self.capture_provider_name
                        or config.provider
                    )

                    attempt = 0

                    while True:
                        result = self.capture_executor.execute(
                            request,
                            provider_name=provider_name,
                        )

                        if not result.failed:
                            break

                        if attempt >= config.retry_limit:
                            raise ValueError(
                                result.error
                                or result.message
                                or "Capture provider failed."
                            )

                        attempt += 1
                        retries_attempted += 1

                        if config.retry_delay_seconds:
                            self.sleep_fn(
                                config.retry_delay_seconds
                            )

                    if result.waiting:
                        captures_waiting = 1

                    elif result.successful:
                        matches_captured = 1
                        bytes_written = result.bytes_written or 0

                        workflow = self.synchronise(root)

        except Exception as exc:
            summary = CaptureIterationSummary(
                started_at=started_at,
                finished_at=datetime.now(),
                status="failed",
                retries_attempted=retries_attempted,
                errors=1,
            )
            self.last_capture_summary = summary

            self._record_capture_summary(
                root=root,
                provider=provider_name,
                match_id=match_id,
                summary=summary,
                error_detail=str(exc),
            )
            raise

        summary = CaptureIterationSummary(
            started_at=started_at,
            finished_at=datetime.now(),
            status=workflow.status,
            matches_captured=matches_captured,
            bytes_written=bytes_written,
            captures_waiting=captures_waiting,
            retries_attempted=retries_attempted,
        )
        self.last_capture_summary = summary

        self._record_capture_summary(
            root=root,
            provider=provider_name,
            match_id=match_id,
            summary=summary,
        )

        return workflow

    def _record_capture_summary(
        self,
        *,
        root: str | Path,
        provider: Optional[str],
        match_id: Optional[int],
        summary: CaptureIterationSummary,
        error_detail: Optional[str] = None,
    ) -> None:
        provider_name = provider

        if not provider_name:
            try:
                provider_name = (
                    self.capture_config_service.load(root).provider
                )
            except Exception:
                provider_name = "unknown"

        db = self.db_session_factory()

        try:
            self.history_service.record(
                db,
                capture_root=root,
                provider=provider_name,
                match_id=match_id,
                summary=summary,
                error_detail=error_detail,
            )
        except Exception:
            rollback = getattr(db, "rollback", None)

            if callable(rollback):
                rollback()

            raise
        finally:
            db.close()

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
