from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

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

    Behaviour:
    - no fixtures: reset and do nothing;
    - new fixture count: capture immediately;
    - successful capture with prices: mark that fixture count handled;
    - successful capture with zero prices: retry after a cooldown;
    - failed capture: leave the fixture count retryable on the next cycle.
    """

    def __init__(
        self,
        *,
        zero_price_retry_seconds: float = 1800.0,
        now_provider: Optional[
            Callable[[], datetime]
        ] = None,
    ) -> None:
        self.zero_price_retry_seconds = max(
            60.0,
            float(zero_price_retry_seconds),
        )
        self._now_provider = (
            now_provider
            or datetime.utcnow
        )
        self._last_fixture_count = 0
        self._last_capture_at = None
        self._last_zero_price_count = 0
        self._last_zero_price_at = None

    def reset(self) -> None:
        self._last_fixture_count = 0
        self._last_capture_at = None
        self._last_zero_price_count = 0
        self._last_zero_price_at = None

    def _now(self) -> datetime:
        return self._now_provider()

    def _zero_price_retry_due(
        self,
        *,
        count: int,
        now: datetime,
    ) -> bool:
        if count != self._last_zero_price_count:
            return True

        if self._last_zero_price_at is None:
            return True

        next_retry = (
            self._last_zero_price_at
            + timedelta(
                seconds=self.zero_price_retry_seconds
            )
        )

        return now >= next_retry

    def consider(
        self,
        *,
        future_fixtures: int,
    ) -> AutomaticOddsCaptureTriggerResult:
        count = max(
            0,
            int(future_fixtures),
        )

        now = self._now()

        if count == 0:
            self.reset()

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
                    "Future fixture count is unchanged "
                    "and already has captured prices."
                ),
            )

        if not self._zero_price_retry_due(
            count=count,
            now=now,
        ):
            next_retry = (
                self._last_zero_price_at
                + timedelta(
                    seconds=self.zero_price_retry_seconds
                )
            )

            return AutomaticOddsCaptureTriggerResult(
                triggered=False,
                ready=True,
                future_fixtures=count,
                captured_at=self._last_capture_at,
                extracted_prices=0,
                stored_prices=0,
                message=(
                    "Paddy Power returned no prices "
                    "for these fixtures recently. "
                    "Automatic retry is cooling down "
                    f"until {next_retry.isoformat()}."
                ),
            )

        db = SessionLocal()

        try:
            result = (
                run_existing_paddy_power_capture(
                    db
                )
            )

            captured_at = now.isoformat()

            if not result.ready:
                return AutomaticOddsCaptureTriggerResult(
                    triggered=True,
                    ready=False,
                    future_fixtures=count,
                    captured_at=captured_at,
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

            self._last_capture_at = captured_at

            if extracted_prices > 0:
                self._last_fixture_count = count
                self._last_zero_price_count = 0
                self._last_zero_price_at = None
                message = (
                    "Automatic Paddy Power capture "
                    "completed after fixture discovery."
                )
            else:
                self._last_zero_price_count = count
                self._last_zero_price_at = now
                message = (
                    "Paddy Power capture completed but "
                    "no prices were available yet. "
                    "The same fixtures will be retried "
                    "after the zero-price cooldown."
                )

            return AutomaticOddsCaptureTriggerResult(
                triggered=True,
                ready=True,
                future_fixtures=count,
                captured_at=captured_at,
                extracted_prices=extracted_prices,
                stored_prices=stored_prices,
                message=message,
            )

        except Exception as exc:
            return AutomaticOddsCaptureTriggerResult(
                triggered=True,
                ready=False,
                future_fixtures=count,
                captured_at=now.isoformat(),
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
