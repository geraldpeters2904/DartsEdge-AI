from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import sleep
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.services.bookmaker_capture_types import (
    BookmakerCaptureReport,
)


@dataclass(frozen=True)
class CaptureManagerStatus:
    running: bool
    cycles: int
    successful_cycles: int
    failed_cycles: int
    challenge_cycles: int
    last_started_at: Optional[datetime]
    last_finished_at: Optional[datetime]
    last_message: str
    last_error: Optional[str]
    total_extracted_prices: int
    total_stored_prices: int
    total_unchanged_prices: int
    total_skipped_prices: int


class BookmakerCaptureManager:
    def __init__(
        self,
        *,
        capture_once: Callable[
            [Session],
            BookmakerCaptureReport,
        ],
        poll_seconds: float = 180.0,
        retry_seconds: float = 30.0,
        max_consecutive_failures: int = 5,
        stop_on_challenge: bool = True,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self.capture_once = capture_once
        self.poll_seconds = max(
            1.0,
            float(
                poll_seconds
            ),
        )
        self.retry_seconds = max(
            1.0,
            float(
                retry_seconds
            ),
        )
        self.max_consecutive_failures = max(
            1,
            int(
                max_consecutive_failures
            ),
        )
        self.stop_on_challenge = bool(
            stop_on_challenge
        )
        self.sleeper = sleeper

        self._running = False
        self._stop_requested = False
        self._cycles = 0
        self._successful_cycles = 0
        self._failed_cycles = 0
        self._challenge_cycles = 0
        self._last_started_at = None
        self._last_finished_at = None
        self._last_message = (
            "Capture manager has not started."
        )
        self._last_error = None
        self._total_extracted_prices = 0
        self._total_stored_prices = 0
        self._total_unchanged_prices = 0
        self._total_skipped_prices = 0

    def status(
        self,
    ) -> CaptureManagerStatus:
        return CaptureManagerStatus(
            running=self._running,
            cycles=self._cycles,
            successful_cycles=(
                self._successful_cycles
            ),
            failed_cycles=(
                self._failed_cycles
            ),
            challenge_cycles=(
                self._challenge_cycles
            ),
            last_started_at=(
                self._last_started_at
            ),
            last_finished_at=(
                self._last_finished_at
            ),
            last_message=(
                self._last_message
            ),
            last_error=(
                self._last_error
            ),
            total_extracted_prices=(
                self._total_extracted_prices
            ),
            total_stored_prices=(
                self._total_stored_prices
            ),
            total_unchanged_prices=(
                self._total_unchanged_prices
            ),
            total_skipped_prices=(
                self._total_skipped_prices
            ),
        )

    def request_stop(
        self,
    ) -> None:
        self._stop_requested = True
        self._last_message = (
            "Stop requested."
        )

    def run_cycle(
        self,
        db: Session,
    ) -> BookmakerCaptureReport:
        self._cycles += 1
        self._last_started_at = (
            datetime.utcnow()
        )
        self._last_error = None

        try:
            report = self.capture_once(
                db
            )
        except Exception as exc:
            self._failed_cycles += 1
            self._last_finished_at = (
                datetime.utcnow()
            )
            self._last_error = str(
                exc
            )
            self._last_message = (
                "Capture cycle failed."
            )
            raise

        self._last_finished_at = (
            datetime.utcnow()
        )

        self._total_extracted_prices += (
            int(
                report.extracted_prices
            )
        )
        self._total_stored_prices += (
            int(
                report.stored_prices
            )
        )
        self._total_unchanged_prices += (
            int(
                report.unchanged_prices
            )
        )
        self._total_skipped_prices += (
            int(
                report.skipped_prices
            )
        )

        if report.challenge_detected:
            self._challenge_cycles += 1
            self._last_message = (
                report.message
            )
        else:
            self._successful_cycles += 1
            self._last_message = (
                report.message
            )

        return report

    def run_forever(
        self,
        *,
        session_factory: Callable[
            [],
            Session,
        ],
        max_cycles: Optional[
            int
        ] = None,
    ) -> CaptureManagerStatus:
        if self._running:
            raise RuntimeError(
                "Capture manager is already running."
            )

        self._running = True
        self._stop_requested = False

        consecutive_failures = 0

        try:
            while not self._stop_requested:
                if (
                    max_cycles is not None
                    and self._cycles
                    >= int(
                        max_cycles
                    )
                ):
                    break

                db = session_factory()

                try:
                    try:
                        report = (
                            self.run_cycle(
                                db
                            )
                        )
                    except Exception:
                        consecutive_failures += 1

                        if (
                            consecutive_failures
                            >= self.max_consecutive_failures
                        ):
                            self._last_message = (
                                "Capture manager stopped after too many consecutive failures."
                            )
                            break

                        self.sleeper(
                            self.retry_seconds
                        )
                        continue

                    consecutive_failures = 0

                    if (
                        report.challenge_detected
                        and self.stop_on_challenge
                    ):
                        self._last_message = (
                            "Capture manager stopped because a verification challenge was detected."
                        )
                        break

                finally:
                    try:
                        db.close()
                    except Exception:
                        pass

                if not self._stop_requested:
                    self.sleeper(
                        self.poll_seconds
                    )

        finally:
            self._running = False

        return self.status()
