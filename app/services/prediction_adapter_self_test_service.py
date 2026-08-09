
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.fixture_prediction_adapter_service import (
    predict_fixture,
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
            message=(
                "No completed MODUS fixture is available for diagnostic testing."
            ),
        )

    result = predict_fixture(
        db,
        fixture_id=int(
            fixture.id
        ),
    )

    if not result.ready:
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
            model_confidence=result.model_confidence,
            minimum_history_matches=result.minimum_history_matches,
            model_name=result.model_name,
            message=(
                "Prediction adapter resolved but did not return a usable "
                f"probability: {result.reason}"
            ),
        )

    return PredictionAdapterSelfTestReport(
        fixture_id=int(
            fixture.id
        ),
        fixture_date=fixture.date,
        player_a=fixture.player_a,
        player_b=fixture.player_b,
        ready=True,
        player_a_probability=result.player_a_probability,
        player_b_probability=result.player_b_probability,
        player_a_fair_odds=result.player_a_fair_odds,
        player_b_fair_odds=result.player_b_fair_odds,
        model_confidence=result.model_confidence,
        minimum_history_matches=result.minimum_history_matches,
        model_name=result.model_name,
        message=(
            "Prediction adapter self-test completed successfully."
        ),
    )
