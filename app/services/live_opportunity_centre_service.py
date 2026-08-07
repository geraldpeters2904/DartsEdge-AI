from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.opportunity_snapshot import OpportunitySnapshot
from app.services.prediction_centre_service import build_prediction_centre


@dataclass(frozen=True)
class LiveOpportunity:
    fixture_id: int
    fixture_date: object
    tournament: str
    player_a: str
    player_b: str
    selection: str
    bookmaker: Optional[str]
    decimal_odds: Optional[float]
    decision_score: int
    decision_grade: str
    recommendation: str
    model_probability: float
    model_confidence: float
    expected_value_percent: float
    edge_percent: float
    consensus_score: Optional[float]
    steam_direction: Optional[str]
    steam_strength: Optional[str]
    coordinated_move: bool
    suggested_stake: float
    lifecycle_state: str
    age_minutes: Optional[int]


def _state(
    *,
    current_score: int,
    first_score: int,
    peak_score: int,
    age_minutes: int,
) -> str:
    if age_minutes < 10:
        return "NEW"

    if current_score >= 90 and current_score >= peak_score:
        return "PEAK"

    if current_score >= 80 and age_minutes >= 20:
        return "MATURE"

    if current_score >= first_score + 5:
        return "BUILDING"

    if current_score <= peak_score - 8:
        return "DECLINING"

    return "BUILDING"


def _history(
    db: Session,
    fixture_id: int,
):
    return (
        db.query(OpportunitySnapshot)
        .filter(
            OpportunitySnapshot.fixture_id == fixture_id
        )
        .order_by(
            OpportunitySnapshot.captured_at.asc(),
            OpportunitySnapshot.id.asc(),
        )
        .all()
    )


def _persist_if_changed(
    db: Session,
    *,
    fixture,
    opportunity,
    assessment,
    price,
    decision,
    lifecycle_state: str,
) -> bool:
    history = _history(
        db,
        fixture.id,
    )

    latest = history[-1] if history else None

    comparable = (
        int(decision["score"]),
        str(decision["recommendation"]),
        round(float(price.decimal_odds), 4) if price else None,
        round(float(decision.get("consensus_score")), 2)
        if decision.get("consensus_score") is not None
        else None,
        str(decision.get("steam_direction") or ""),
        str(decision.get("steam_strength") or ""),
        lifecycle_state,
    )

    if latest is not None:
        latest_comparable = (
            int(latest.decision_score),
            str(latest.recommendation),
            round(float(latest.decimal_odds), 4)
            if latest.decimal_odds is not None
            else None,
            round(float(latest.consensus_score), 2)
            if latest.consensus_score is not None
            else None,
            str(latest.steam_direction or ""),
            str(latest.steam_strength or ""),
            str(latest.lifecycle_state),
        )

        if comparable == latest_comparable:
            return False

    row = OpportunitySnapshot(
        fixture_id=fixture.id,
        fixture_date=fixture.date,
        tournament=fixture.tournament or "Unknown",
        player_a=fixture.player_a,
        player_b=fixture.player_b,
        selection=opportunity["selection"],
        market="match_winner",
        bookmaker=price.bookmaker if price else None,
        decimal_odds=float(price.decimal_odds) if price else None,
        model_probability=float(opportunity.get("probability") or 0.0),
        model_confidence=float(opportunity.get("model_confidence") or 0.0),
        expected_value_percent=float(
            assessment.expected_value_percent
        ),
        edge_percent=float(
            assessment.edge_percent
        ),
        decision_score=int(decision["score"]),
        decision_grade=str(decision["grade"]),
        recommendation=str(decision["recommendation"]),
        consensus_score=(
            float(decision["consensus_score"])
            if decision.get("consensus_score") is not None
            else None
        ),
        steam_direction=decision.get("steam_direction"),
        steam_strength=decision.get("steam_strength"),
        coordinated_move=bool(decision.get("coordinated_move")),
        lifecycle_state=lifecycle_state,
        suggested_stake=float(
            decision.get(
                "strategy_suggested_stake",
                assessment.recommended_stake,
            )
            or 0.0
        ),
        captured_at=datetime.utcnow(),
    )

    db.add(row)
    db.commit()
    return True


def build_live_opportunity_centre(
    db: Session,
    *,
    limit: int = 30,
    persist: bool = True,
) -> dict:
    centre = build_prediction_centre(
        db,
        limit=limit,
    )

    now = datetime.utcnow()
    rows = []

    for card in centre["cards"]:
        decision = card.get("decision_intelligence")
        opportunity = card.get("opportunity")
        assessment = card.get("assessment")
        fixture = card.get("fixture")
        price = card.get("price")

        if not (
            decision
            and opportunity
            and assessment
            and fixture
        ):
            continue

        history = _history(
            db,
            fixture.id,
        )

        if history:
            first = history[0]
            peak_score = max(
                item.decision_score
                for item in history
            )
            age_minutes = max(
                0,
                int(
                    (
                        now
                        - first.captured_at
                    ).total_seconds()
                    / 60
                ),
            )
            first_score = int(
                first.decision_score
            )
        else:
            age_minutes = 0
            first_score = int(
                decision["score"]
            )
            peak_score = int(
                decision["score"]
            )

        lifecycle = _state(
            current_score=int(
                decision["score"]
            ),
            first_score=first_score,
            peak_score=max(
                peak_score,
                int(
                    decision["score"]
                ),
            ),
            age_minutes=age_minutes,
        )

        if persist:
            _persist_if_changed(
                db,
                fixture=fixture,
                opportunity=opportunity,
                assessment=assessment,
                price=price,
                decision=decision,
                lifecycle_state=lifecycle,
            )

        rows.append(
            LiveOpportunity(
                fixture_id=int(
                    fixture.id
                ),
                fixture_date=fixture.date,
                tournament=str(
                    fixture.tournament
                    or "Unknown"
                ),
                player_a=str(
                    fixture.player_a
                ),
                player_b=str(
                    fixture.player_b
                ),
                selection=str(
                    opportunity["selection"]
                ),
                bookmaker=(
                    str(price.bookmaker)
                    if price
                    else None
                ),
                decimal_odds=(
                    float(price.decimal_odds)
                    if price
                    else None
                ),
                decision_score=int(
                    decision["score"]
                ),
                decision_grade=str(
                    decision["grade"]
                ),
                recommendation=str(
                    decision["recommendation"]
                ),
                model_probability=float(
                    opportunity.get("probability")
                    or 0.0
                ),
                model_confidence=float(
                    opportunity.get("model_confidence")
                    or 0.0
                ),
                expected_value_percent=float(
                    assessment.expected_value_percent
                ),
                edge_percent=float(
                    assessment.edge_percent
                ),
                consensus_score=(
                    float(
                        decision["consensus_score"]
                    )
                    if decision.get("consensus_score")
                    is not None
                    else None
                ),
                steam_direction=decision.get(
                    "steam_direction"
                ),
                steam_strength=decision.get(
                    "steam_strength"
                ),
                coordinated_move=bool(
                    decision.get("coordinated_move")
                ),
                suggested_stake=float(
                    decision.get(
                        "strategy_suggested_stake",
                        assessment.recommended_stake,
                    )
                    or 0.0
                ),
                lifecycle_state=lifecycle,
                age_minutes=age_minutes,
            )
        )

    rows.sort(
        key=lambda item: (
            item.decision_score,
            item.expected_value_percent,
            item.edge_percent,
        ),
        reverse=True,
    )

    return {
        "centre_date": centre["centre_date"],
        "opportunities": tuple(rows),
        "opportunity_count": len(rows),
        "bet_count": sum(
            item.recommendation == "BET"
            for item in rows
        ),
        "watch_count": sum(
            item.recommendation == "WATCH"
            for item in rows
        ),
        "mature_count": sum(
            item.lifecycle_state
            in {"MATURE", "PEAK"}
            for item in rows
        ),
        "top_opportunity": (
            rows[0]
            if rows
            else None
        ),
        "portfolio": centre["portfolio"],
        "active_strategy": centre["active_strategy"],
    }
