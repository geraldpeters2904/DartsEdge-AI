from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.opportunity_identity import OpportunityIdentity
from app.models.opportunity_snapshot import OpportunitySnapshot


@dataclass(frozen=True)
class OpportunityTimelinePoint:
    captured_at: datetime
    decision_score: int
    recommendation: str
    lifecycle_state: str
    decimal_odds: Optional[float]
    expected_value_percent: Optional[float]
    consensus_score: Optional[float]
    steam_direction: Optional[str]
    steam_strength: Optional[str]


@dataclass(frozen=True)
class OpportunityEvent:
    captured_at: datetime
    event_type: str
    message: str


@dataclass(frozen=True)
class OpportunityReplay:
    opportunity_id: str
    fixture_id: int
    player_a: str
    player_b: str
    selection: str
    bookmaker: Optional[str]
    first_seen_at: datetime
    last_seen_at: datetime
    age_minutes: int
    first_score: int
    latest_score: int
    peak_score: int
    peak_at: datetime
    latest_state: str
    timeline: tuple[OpportunityTimelinePoint, ...]
    events: tuple[OpportunityEvent, ...]


def _opportunity_id(*, fixture_id: int, fixture_date) -> str:
    date_part = (
        fixture_date.strftime("%Y%m%d")
        if fixture_date
        else "00000000"
    )
    return f"OPP-{date_part}-{int(fixture_id):06d}"


def get_or_create_identity(
    db: Session,
    *,
    fixture_id: int,
    fixture_date,
) -> OpportunityIdentity:
    existing = (
        db.query(OpportunityIdentity)
        .filter(OpportunityIdentity.fixture_id == int(fixture_id))
        .first()
    )

    if existing is not None:
        return existing

    row = OpportunityIdentity(
        opportunity_id=_opportunity_id(
            fixture_id=fixture_id,
            fixture_date=fixture_date,
        ),
        fixture_id=int(fixture_id),
    )

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _event(captured_at, event_type, message) -> OpportunityEvent:
    return OpportunityEvent(
        captured_at=captured_at,
        event_type=event_type,
        message=message,
    )


def build_events(
    snapshots: Iterable[OpportunitySnapshot],
) -> tuple[OpportunityEvent, ...]:
    snapshots = list(snapshots)

    if not snapshots:
        return ()

    events = [
        _event(
            snapshots[0].captured_at,
            "created",
            f"Opportunity created at Decision {snapshots[0].decision_score}.",
        )
    ]

    previous = snapshots[0]

    for current in snapshots[1:]:
        if current.lifecycle_state != previous.lifecycle_state:
            events.append(
                _event(
                    current.captured_at,
                    "lifecycle",
                    (
                        f"Lifecycle changed "
                        f"{previous.lifecycle_state} → "
                        f"{current.lifecycle_state}."
                    ),
                )
            )

        if current.recommendation != previous.recommendation:
            events.append(
                _event(
                    current.captured_at,
                    "recommendation",
                    (
                        f"Recommendation changed "
                        f"{previous.recommendation} → "
                        f"{current.recommendation}."
                    ),
                )
            )

        if current.decision_score >= 80 > previous.decision_score:
            events.append(
                _event(
                    current.captured_at,
                    "threshold",
                    "Decision Score crossed 80.",
                )
            )

        if current.decision_score >= 90 > previous.decision_score:
            events.append(
                _event(
                    current.captured_at,
                    "threshold",
                    "Decision Score crossed 90.",
                )
            )

        if (
            current.consensus_score is not None
            and previous.consensus_score is not None
            and current.consensus_score >= 90
            and previous.consensus_score < 90
        ):
            events.append(
                _event(
                    current.captured_at,
                    "consensus",
                    "Bookmaker consensus crossed 90.",
                )
            )

        if current.coordinated_move and not previous.coordinated_move:
            events.append(
                _event(
                    current.captured_at,
                    "steam",
                    (
                        "Coordinated market move detected: "
                        f"{current.steam_strength or 'market'} "
                        f"{current.steam_direction or 'move'}."
                    ),
                )
            )

        if (
            current.decimal_odds is not None
            and previous.decimal_odds is not None
            and abs(
                float(current.decimal_odds)
                - float(previous.decimal_odds)
            ) >= 0.05
        ):
            direction = (
                "improved"
                if current.decimal_odds > previous.decimal_odds
                else "shortened"
            )

            events.append(
                _event(
                    current.captured_at,
                    "odds",
                    (
                        f"Price {direction} from "
                        f"{previous.decimal_odds:.2f} "
                        f"to {current.decimal_odds:.2f}."
                    ),
                )
            )

        previous = current

    return tuple(events)


def build_opportunity_replay(
    db: Session,
    *,
    fixture_id: int,
) -> Optional[OpportunityReplay]:
    snapshots = (
        db.query(OpportunitySnapshot)
        .filter(OpportunitySnapshot.fixture_id == int(fixture_id))
        .order_by(
            OpportunitySnapshot.captured_at.asc(),
            OpportunitySnapshot.id.asc(),
        )
        .all()
    )

    if not snapshots:
        return None

    first = snapshots[0]
    latest = snapshots[-1]

    identity = get_or_create_identity(
        db,
        fixture_id=fixture_id,
        fixture_date=first.fixture_date,
    )

    peak = max(
        snapshots,
        key=lambda item: (
            item.decision_score,
            -item.id,
        ),
    )

    age_minutes = max(
        0,
        int(
            (
                latest.captured_at
                - first.captured_at
            ).total_seconds()
            / 60
        ),
    )

    timeline = tuple(
        OpportunityTimelinePoint(
            captured_at=item.captured_at,
            decision_score=int(item.decision_score),
            recommendation=item.recommendation,
            lifecycle_state=item.lifecycle_state,
            decimal_odds=(
                float(item.decimal_odds)
                if item.decimal_odds is not None
                else None
            ),
            expected_value_percent=(
                float(item.expected_value_percent)
                if item.expected_value_percent is not None
                else None
            ),
            consensus_score=(
                float(item.consensus_score)
                if item.consensus_score is not None
                else None
            ),
            steam_direction=item.steam_direction,
            steam_strength=item.steam_strength,
        )
        for item in snapshots
    )

    return OpportunityReplay(
        opportunity_id=identity.opportunity_id,
        fixture_id=int(fixture_id),
        player_a=first.player_a,
        player_b=first.player_b,
        selection=first.selection,
        bookmaker=first.bookmaker,
        first_seen_at=first.captured_at,
        last_seen_at=latest.captured_at,
        age_minutes=age_minutes,
        first_score=int(first.decision_score),
        latest_score=int(latest.decision_score),
        peak_score=int(peak.decision_score),
        peak_at=peak.captured_at,
        latest_state=latest.lifecycle_state,
        timeline=timeline,
        events=build_events(snapshots),
    )
