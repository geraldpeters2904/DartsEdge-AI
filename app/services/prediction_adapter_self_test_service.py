
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.prediction_context_service import (
    build_prediction_context,
)


@dataclass(frozen=True)
class PredictionAdapterSelfTestReport:
    fixture_id: Optional[int]
    fixture_date: Optional[object]
    player_a: Optional[str]
    player_b: Optional[str]
    ready: bool
    player_a_probability: Optional[float]
    player_b_probability: Optional[float]
    player_a_fair_odds: Optional[float]
    player_b_fair_odds: Optional[float]
    model_confidence: Optional[float]
    minimum_history_matches: int
    model_name: Optional[str]
    model_version: Optional[str]
    predicted_winner: Optional[str]
    message: str


def _recent_completed_modus_fixture(
    db: Session,
) -> Optional[Match]:
    return (
        db.query(Match)
        .filter(
            Match.status == "completed",
            Match.tournament.ilike("%MODUS%"),
        )
        .order_by(
            Match.date.desc(),
            Match.id.desc(),
        )
        .first()
    )


def _fair_odds(
    probability: Optional[float],
) -> Optional[float]:
    if probability is None:
        return None

    value = float(probability)

    if value <= 0.0 or value >= 1.0:
        return None

    return round(
        1.0 / value,
        4,
    )


def run_prediction_adapter_self_test(
    db: Session,
) -> PredictionAdapterSelfTestReport:
    fixture = _recent_completed_modus_fixture(
        db
    )

    if fixture is None:
        return PredictionAdapterSelfTestReport(
            fixture_id=None,
            fixture_date=None,
            player_a=None,
            player_b=None,
            ready=False,
            player_a_probability=None,
            player_b_probability=None,
            player_a_fair_odds=None,
            player_b_fair_odds=None,
            model_confidence=None,
            minimum_history_matches=0,
            model_name=None,
            model_version=None,
            predicted_winner=None,
            message=(
                "No completed MODUS fixture is available for diagnostic testing."
            ),
        )

    try:
        context = build_prediction_context(
            db,
            int(fixture.id),
        )
    except Exception as exc:
        return PredictionAdapterSelfTestReport(
            fixture_id=int(
                fixture.id
            ),
            fixture_date=fixture.date,
            player_a=fixture.player_a,
            player_b=fixture.player_b,
            ready=False,
            player_a_probability=None,
            player_b_probability=None,
            player_a_fair_odds=None,
            player_b_fair_odds=None,
            model_confidence=None,
            minimum_history_matches=0,
            model_name=None,
            model_version=None,
            predicted_winner=None,
            message=(
                "Direct prediction context build failed: "
                + str(exc)
            ),
        )

    minimum_history = min(
        int(
            context.player_a_history_matches
        ),
        int(
            context.player_b_history_matches
        ),
    )

    return PredictionAdapterSelfTestReport(
        fixture_id=int(
            fixture.id
        ),
        fixture_date=fixture.date,
        player_a=context.player_a_name,
        player_b=context.player_b_name,
        ready=True,
        player_a_probability=float(
            context.player_a_probability
        ),
        player_b_probability=float(
            context.player_b_probability
        ),
        player_a_fair_odds=_fair_odds(
            context.player_a_probability
        ),
        player_b_fair_odds=_fair_odds(
            context.player_b_probability
        ),
        model_confidence=float(
            context.model_confidence
        ),
        minimum_history_matches=minimum_history,
        model_name=context.model_name,
        model_version=context.model_version,
        predicted_winner=context.predicted_winner,
        message=(
            "Direct registered-model self-test completed successfully."
        ),
    )
