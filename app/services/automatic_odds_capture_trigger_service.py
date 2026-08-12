from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.db import SessionLocal
from app.services.paddy_power_live_bridge import (
    run_existing_paddy_power_capture,
)


@dataclass(frozen=True)
class AutomaticOddsCaptureTriggerResult:
    triggered: bool
    ready: bool
    future_fixtures: int
    captured_at: Optional[str]
    extracted_prices: int
    stored_prices: int
    message: str
    error: Optional[str] = None


class AutomaticOddsCaptureTrigger:
    """
    Trigger Paddy Power capture when useful forward-fixture
    state changes.

    This avoids launching a bookmaker browser on every
    forward-schedule polling cycle.

    A successful capture that returns zero prices is not
    treated as handled, so the same fixture count will be
    retried on the next discovery cycle.
    """

    def __init__(self) -> None:
        self._last_fixture_count = 0
        self._last_capture_at = None

    def reset(self) -> None:
        self._last_fixture_count = 0
        self._last_capture_at = None

    def consider(
        self,
        *,
        future_fixtures: int,
    ) -> AutomaticOddsCaptureTriggerResult:
        count = max(
            0,
            int(future_fixtures),
        )

        if count == 0:
            self._last_fixture_count = 0
            self._last_capture_at = None

            return AutomaticOddsCaptureTriggerResult(
                triggered=False,
                ready=True,
                future_fixtures=0,
                captured_at=None,
                extracted_prices=0,
                stored_prices=0,
                message=(
                    "Odds capture not required because "
                    "no future fixtures are available."
                ),
            )

        if count == self._last_fixture_count:
            return AutomaticOddsCaptureTriggerResult(
                triggered=False,
                ready=True,
                future_fixtures=count,
                captured_at=self._last_capture_at,
                extracted_prices=0,
                stored_prices=0,
                message=(
                    "Future fixture count is unchanged; "
                    "automatic odds capture was not repeated."
                ),
            )

        db = SessionLocal()

        try:
            result = (
                run_existing_paddy_power_capture(
                    db
                )
            )

            now = datetime.utcnow().isoformat()

            if not result.ready:
                return AutomaticOddsCaptureTriggerResult(
                    triggered=True,
                    ready=False,
                    future_fixtures=count,
                    captured_at=now,
                    extracted_prices=(
                        result.report.extracted_prices
                        if result.report is not None
                        else 0
                    ),
                    stored_prices=(
                        result.report.stored_prices
                        if result.report is not None
                        else 0
                    ),
                    message=result.message,
                    error=result.error,
                )

            report = result.report

            extracted_prices = (
                report.extracted_prices
                if report is not None
                else 0
            )

            stored_prices = (
                report.stored_prices
                if report is not None
                else 0
            )

            self._last_capture_at = now

            if extracted_prices > 0:
                self._last_fixture_count = count

                message = (
                    "Automatic Paddy Power capture "
                    "completed after fixture discovery."
                )
            else:
                message = (
                    "Paddy Power capture completed but "
                    "no prices were available yet. "
                    "The same fixtures will be retried "
                    "on the next discovery cycle."
                )

            return AutomaticOddsCaptureTriggerResult(
                triggered=True,
                ready=True,
                future_fixtures=count,
                captured_at=now,
                extracted_prices=extracted_prices,
                stored_prices=stored_prices,
                message=message,
            )

        except Exception as exc:
            return AutomaticOddsCaptureTriggerResult(
                triggered=True,
                ready=False,
                future_fixtures=count,
                captured_at=datetime.utcnow().isoformat(),
                extracted_prices=0,
                stored_prices=0,
                message=(
                    "Automatic Paddy Power capture failed."
                ),
                error=str(exc),
            )

        finally:
            db.close()


automatic_odds_capture_trigger = (
    AutomaticOddsCaptureTrigger()
)
