
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.services.fixture_edge_service import (
    build_fixture_edge_rows,
)
from app.services.forward_schedule_monitor_service import (
    forward_schedule_monitor,
)
from app.services.live_edge_monitor_service import (
    live_edge_monitor,
)
from app.services.upcoming_fixture_intelligence_service import (
    build_upcoming_fixture_intelligence,
)


@dataclass(frozen=True)
class PredictionReadinessRow:
    fixture_id: int
    fixture_date: date
    player_a: str
    player_b: str
    history_ready: bool
    history_label: str
    minimum_history_matches: int
    model_ready: bool
    odds_ready: bool
    edge_ready: bool
    best_verdict: str
    priced_rows: int
    value_rows: int
    message: str


@dataclass(frozen=True)
class PredictionReadinessDashboard:
    fixture_count: int
    history_ready_count: int
    model_ready_count: int
    odds_ready_count: int
    edge_ready_count: int
    value_fixture_count: int
    forward_monitor_running: bool
    forward_monitor_runs: int
    forward_monitor_failures: int
    forward_monitor_future_fixtures: int
    live_edge_monitor_running: bool
    live_edge_monitor_runs: int
    live_edge_monitor_failures: int
    live_edge_last_priced_rows: int
    live_edge_last_value_rows: int
    rows: tuple[PredictionReadinessRow, ...]


_VERDICT_RANK = {
    "NO MARKET": 0,
    "NO BET": 1,
    "WATCH": 2,
    "VALUE": 3,
    "STRONG VALUE": 4,
}


def _best_verdict(verdicts) -> str:
    values = tuple(
        str(value)
        for value in verdicts
        if value
    )

    if not values:
        return "NO MARKET"

    return max(
        values,
        key=lambda value: _VERDICT_RANK.get(
            value,
            -1,
        ),
    )


def build_prediction_readiness_dashboard(
    db: Session,
    *,
    today: Optional[date] = None,
) -> PredictionReadinessDashboard:
    upcoming = build_upcoming_fixture_intelligence(
        db,
        today=today,
    )

    edge_rows = build_fixture_edge_rows(
        db,
        today=today,
    )

    by_fixture = {}

    for row in edge_rows:
        by_fixture.setdefault(
            row.fixture_id,
            [],
        ).append(
            row
        )

    output = []

    for fixture in upcoming:
        rows = by_fixture.get(
            fixture.fixture_id,
            [],
        )

        model_ready = any(
            row.model_probability is not None
            for row in rows
        )

        odds_ready = any(
            row.bookmaker_odds is not None
            for row in rows
        )

        edge_ready = any(
            row.edge_percent is not None
            for row in rows
        )

        priced_rows = sum(
            1
            for row in rows
            if row.bookmaker_odds is not None
        )

        value_rows = sum(
            1
            for row in rows
            if row.classification in {
                "VALUE",
                "STRONG VALUE",
            }
        )

        verdict = _best_verdict(
            row.classification
            for row in rows
        )

        if not fixture.history_ready:
            message = (
                "Historical depth is below the preferred prediction threshold."
            )
        elif not model_ready:
            message = (
                "Historical depth is ready; awaiting model probability."
            )
        elif not odds_ready:
            message = (
                "Model is ready; awaiting bookmaker odds."
            )
        elif not edge_ready:
            message = (
                "Model and odds are present; edge calculation is incomplete."
            )
        else:
            message = (
                "Prediction, market price and edge calculation are ready."
            )

        output.append(
            PredictionReadinessRow(
                fixture_id=fixture.fixture_id,
                fixture_date=fixture.fixture_date,
                player_a=fixture.player_a,
                player_b=fixture.player_b,
                history_ready=fixture.history_ready,
                history_label=fixture.readiness_label,
                minimum_history_matches=fixture.minimum_history_matches,
                model_ready=model_ready,
                odds_ready=odds_ready,
                edge_ready=edge_ready,
                best_verdict=verdict,
                priced_rows=priced_rows,
                value_rows=value_rows,
                message=message,
            )
        )

    forward = forward_schedule_monitor.status()
    live_edge = live_edge_monitor.status()

    return PredictionReadinessDashboard(
        fixture_count=len(output),
        history_ready_count=sum(
            row.history_ready
            for row in output
        ),
        model_ready_count=sum(
            row.model_ready
            for row in output
        ),
        odds_ready_count=sum(
            row.odds_ready
            for row in output
        ),
        edge_ready_count=sum(
            row.edge_ready
            for row in output
        ),
        value_fixture_count=sum(
            row.value_rows > 0
            for row in output
        ),
        forward_monitor_running=forward.running,
        forward_monitor_runs=forward.runs,
        forward_monitor_failures=forward.failures,
        forward_monitor_future_fixtures=forward.future_fixtures,
        live_edge_monitor_running=live_edge.running,
        live_edge_monitor_runs=live_edge.runs,
        live_edge_monitor_failures=live_edge.failures,
        live_edge_last_priced_rows=live_edge.last_priced_rows,
        live_edge_last_value_rows=live_edge.last_value_rows,
        rows=tuple(output),
    )
