from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.opportunity_snapshot import (
    OpportunitySnapshot,
)


@dataclass(frozen=True)
class DecisionSafetyOutcomeMetric:
    state: str
    snapshots: int
    settled: int
    wins: int
    losses: int
    total_staked: float
    profit_loss: float
    roi_percent: Optional[float]
    win_rate_percent: Optional[float]
    average_ev_percent: Optional[float]
    average_edge_percent: Optional[float]
    average_odds: Optional[float]
    average_stake: Optional[float]


@dataclass(frozen=True)
class DecisionSafetyOutcomeEvidence:
    total_fixtures: int
    settled_fixtures: int
    states: tuple[
        DecisionSafetyOutcomeMetric,
        ...
    ]
    insufficient_data: bool


def _normalise(value) -> str:
    return " ".join(
        str(value or "")
        .strip()
        .casefold()
        .split()
    )


def _latest_snapshots(
    db: Session,
) -> tuple[OpportunitySnapshot, ...]:
    """
    Return one final persisted opportunity observation per
    fixture.

    Multiple lifecycle snapshots for the same fixture must
    not cause one completed match to be counted repeatedly
    in outcome statistics.
    """
    rows = (
        db.query(OpportunitySnapshot)
        .order_by(
            OpportunitySnapshot.fixture_id.asc(),
            OpportunitySnapshot.captured_at.asc(),
            OpportunitySnapshot.id.asc(),
        )
        .all()
    )

    latest = {}

    for row in rows:
        latest[int(row.fixture_id)] = row

    return tuple(
        latest[key]
        for key in sorted(latest)
    )


def _metric(
    state: str,
    rows,
) -> DecisionSafetyOutcomeMetric:
    snapshots = len(rows)

    settled_rows = [
        item
        for item in rows
        if item["settled"]
    ]

    wins = sum(
        item["won"]
        for item in settled_rows
    )

    losses = sum(
        not item["won"]
        for item in settled_rows
    )

    staked_rows = [
        item
        for item in settled_rows
        if item["stake"] > 0.0
        and item["odds"] is not None
        and item["odds"] > 1.0
    ]

    total_staked = sum(
        item["stake"]
        for item in staked_rows
    )

    profit_loss = 0.0

    for item in staked_rows:
        if item["won"]:
            profit_loss += (
                item["stake"]
                * (
                    item["odds"]
                    - 1.0
                )
            )
        else:
            profit_loss -= item["stake"]

    roi = (
        profit_loss
        / total_staked
        * 100.0
        if total_staked > 0.0
        else None
    )

    win_denominator = (
        wins + losses
    )

    win_rate = (
        wins
        / win_denominator
        * 100.0
        if win_denominator
        else None
    )

    def average(field):
        values = [
            item[field]
            for item in rows
            if item[field] is not None
        ]

        if not values:
            return None

        return (
            sum(values)
            / len(values)
        )

    return DecisionSafetyOutcomeMetric(
        state=state,
        snapshots=snapshots,
        settled=len(settled_rows),
        wins=wins,
        losses=losses,
        total_staked=round(
            total_staked,
            2,
        ),
        profit_loss=round(
            profit_loss,
            2,
        ),
        roi_percent=(
            round(
                roi,
                2,
            )
            if roi is not None
            else None
        ),
        win_rate_percent=(
            round(
                win_rate,
                2,
            )
            if win_rate is not None
            else None
        ),
        average_ev_percent=(
            round(
                average(
                    "ev"
                ),
                2,
            )
            if average("ev")
            is not None
            else None
        ),
        average_edge_percent=(
            round(
                average(
                    "edge"
                ),
                2,
            )
            if average("edge")
            is not None
            else None
        ),
        average_odds=(
            round(
                average(
                    "odds"
                ),
                3,
            )
            if average("odds")
            is not None
            else None
        ),
        average_stake=(
            round(
                average(
                    "stake"
                ),
                2,
            )
            if average("stake")
            is not None
            else None
        ),
    )


def build_decision_safety_outcome_evidence(
    db: Session,
) -> DecisionSafetyOutcomeEvidence:
    snapshots = _latest_snapshots(
        db
    )

    observations = []

    for snapshot in snapshots:
        match = (
            db.query(Match)
            .filter(
                Match.id
                == int(
                    snapshot.fixture_id
                )
            )
            .first()
        )

        settled = bool(
            match is not None
            and str(
                match.status
                or ""
            ).strip().casefold()
            == "completed"
            and bool(
                str(
                    match.winner
                    or ""
                ).strip()
            )
        )

        won = False

        if settled:
            won = (
                _normalise(
                    snapshot.selection
                )
                == _normalise(
                    match.winner
                )
            )

        observations.append({
            "state": str(
                snapshot.decision_safety_state
                or "UNKNOWN"
            ).strip().upper(),
            "settled": settled,
            "won": won,
            "stake": max(
                float(
                    snapshot.suggested_stake
                    or 0.0
                ),
                0.0,
            ),
            "odds": (
                float(
                    snapshot.decimal_odds
                )
                if snapshot.decimal_odds
                is not None
                else None
            ),
            "ev": (
                float(
                    snapshot
                    .expected_value_percent
                )
                if snapshot
                .expected_value_percent
                is not None
                else None
            ),
            "edge": (
                float(
                    snapshot.edge_percent
                )
                if snapshot.edge_percent
                is not None
                else None
            ),
        })

    state_order = (
        "NORMAL",
        "CAUTION",
        "HIGH_CAUTION",
        "UNKNOWN",
    )

    metrics = []

    for state in state_order:
        state_rows = [
            row
            for row in observations
            if row["state"] == state
        ]

        metrics.append(
            _metric(
                state,
                state_rows,
            )
        )

    known_states = set(
        state_order
    )

    extra_states = sorted({
        row["state"]
        for row in observations
        if row["state"]
        not in known_states
    })

    for state in extra_states:
        metrics.append(
            _metric(
                state,
                [
                    row
                    for row in observations
                    if row["state"]
                    == state
                ],
            )
        )

    settled_total = sum(
        row["settled"]
        for row in observations
    )

    return DecisionSafetyOutcomeEvidence(
        total_fixtures=len(
            observations
        ),
        settled_fixtures=int(
            settled_total
        ),
        states=tuple(
            metrics
        ),
        insufficient_data=(
            settled_total < 25
        ),
    )
