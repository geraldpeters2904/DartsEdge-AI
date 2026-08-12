from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.forward_schedule_monitor_service import (
    forward_schedule_monitor,
)
from app.services.stale_scheduled_fixture_diagnostic_service import (
    build_stale_scheduled_fixture_diagnostic,
)


@dataclass(frozen=True)
class FixtureAcquisitionReadiness:
    state: str
    ready: bool
    waiting: bool
    stale: bool
    error: bool

    future_scheduled: int
    stale_scheduled: int

    latest_series: Optional[str]
    latest_week: Optional[str]
    last_checked_at: Optional[str]

    explanation: str


def build_fixture_acquisition_readiness(
    db: Session,
    *,
    monitor_status=None,
    today: Optional[date] = None,
) -> FixtureAcquisitionReadiness:
    current_day = (
        today
        or date.today()
    )

    status = (
        monitor_status
        or forward_schedule_monitor.status()
    )

    stale_report = (
        build_stale_scheduled_fixture_diagnostic(
            db,
            today=current_day,
        )
    )

    future_scheduled = int(
        db.query(Match)
        .filter(
            Match.status == "scheduled",
            Match.date >= current_day,
            Match.tournament.ilike(
                "%MODUS%"
            ),
        )
        .count()
    )

    common = {
        "future_scheduled": (
            future_scheduled
        ),
        "stale_scheduled": (
            stale_report.stale_count
        ),
        "latest_series": getattr(
            status,
            "latest_series",
            None,
        ),
        "latest_week": getattr(
            status,
            "latest_week",
            None,
        ),
        "last_checked_at": getattr(
            status,
            "last_run_at",
            None,
        ),
    }

    if getattr(
        status,
        "last_error",
        None,
    ):
        return FixtureAcquisitionReadiness(
            state="ERROR",
            ready=False,
            waiting=False,
            stale=False,
            error=True,
            explanation=(
                "Forward fixture acquisition "
                "encountered an error: "
                + str(status.last_error)
            ),
            **common,
        )

    if not stale_report.healthy:
        return FixtureAcquisitionReadiness(
            state="STALE",
            ready=False,
            waiting=False,
            stale=True,
            error=False,
            explanation=(
                stale_report.explanation
            ),
            **common,
        )

    if future_scheduled > 0:
        return FixtureAcquisitionReadiness(
            state="READY",
            ready=True,
            waiting=False,
            stale=False,
            error=False,
            explanation=(
                f"{future_scheduled} current or "
                "future MODUS fixture(s) are "
                "available for Prediction Centre."
            ),
            **common,
        )

    return FixtureAcquisitionReadiness(
        state="WAITING",
        ready=False,
        waiting=True,
        stale=False,
        error=False,
        explanation=(
            "No current or future MODUS fixtures "
            "are published in the local schedule. "
            "The acquisition monitor is waiting "
            "for the official schedule."
        ),
        **common,
    )
