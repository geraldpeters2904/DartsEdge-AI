
from __future__ import annotations

from app.prediction_config import (
    ACTIVE_PREDICTION_MODEL_NAME,
)

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.opportunity_ranking_service import (
    build_ranked_opportunities,
)


@dataclass(frozen=True)
class FixturePrediction:
    fixture_id: int
    player_a: str
    player_b: str
    player_a_probability: Optional[float]
    player_b_probability: Optional[float]
    player_a_fair_odds: Optional[float]
    player_b_fair_odds: Optional[float]
    model_confidence: Optional[float]
    player_a_history_matches: int
    player_b_history_matches: int
    minimum_history_matches: int
    model_name: Optional[str]
    ready: bool
    reason: str


def _normalise(value: str | None) -> str:
    return " ".join(
        (value or "")
        .strip()
        .casefold()
        .split()
    )


def _fixture_key(
    player_a: str,
    player_b: str,
) -> frozenset[str]:
    return frozenset(
        (
            _normalise(player_a),
            _normalise(player_b),
        )
    )


def _probability(value) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if 0.0 < number < 1.0:
        return number

    if 1.0 <= number <= 100.0:
        return number / 100.0

    return None


def _fair_odds(
    probability: Optional[float],
) -> Optional[float]:
    if probability is None:
        return None

    if probability <= 0.0 or probability >= 1.0:
        return None

    return round(
        1.0 / probability,
        4,
    )


def _match_opportunity(
    opportunities,
    fixture: Match,
):
    by_id = {
        item.get("match_id"): item
        for item in opportunities
        if item.get("match_id")
    }

    direct = by_id.get(
        fixture.id
    )

    if direct is not None:
        return direct

    target = _fixture_key(
        fixture.player_a,
        fixture.player_b,
    )

    for item in opportunities:
        if (
            _fixture_key(
                item.get("player_a", ""),
                item.get("player_b", ""),
            )
            == target
        ):
            return item

    return None


def predict_fixture(
    db: Session,
    *,
    fixture_id: int,
) -> FixturePrediction:
    fixture = (
        db.query(Match)
        .filter(
            Match.id == int(
                fixture_id
            )
        )
        .first()
    )

    if fixture is None:
        return FixturePrediction(
            fixture_id=int(
                fixture_id
            ),
            player_a="",
            player_b="",
            player_a_probability=None,
            player_b_probability=None,
            player_a_fair_odds=None,
            player_b_fair_odds=None,
            model_confidence=None,
            player_a_history_matches=0,
            player_b_history_matches=0,
            minimum_history_matches=0,
            model_name=None,
            ready=False,
            reason="Fixture was not found.",
        )

    opportunities = (
        build_ranked_opportunities(
            db,
            limit=200,
        )
    )

    opportunity = (
        _match_opportunity(
            opportunities,
            fixture,
        )
    )

    if opportunity is None:
        return FixturePrediction(
            fixture_id=int(
                fixture.id
            ),
            player_a=fixture.player_a,
            player_b=fixture.player_b,
            player_a_probability=None,
            player_b_probability=None,
            player_a_fair_odds=None,
            player_b_fair_odds=None,
            model_confidence=None,
            player_a_history_matches=0,
            player_b_history_matches=0,
            minimum_history_matches=0,
            model_name=None,
            ready=False,
            reason=(
                "No ranked prediction opportunity is currently available "
                "for this fixture."
            ),
        )

    probability_a = _probability(
        opportunity.get(
            "probability"
        )
    )

    if probability_a is None:
        return FixturePrediction(
            fixture_id=int(
                fixture.id
            ),
            player_a=fixture.player_a,
            player_b=fixture.player_b,
            player_a_probability=None,
            player_b_probability=None,
            player_a_fair_odds=None,
            player_b_fair_odds=None,
            model_confidence=None,
            player_a_history_matches=int(
                opportunity.get(
                    "player_a_history_matches",
                    0,
                )
                or 0
            ),
            player_b_history_matches=int(
                opportunity.get(
                    "player_b_history_matches",
                    0,
                )
                or 0
            ),
            minimum_history_matches=min(
                int(
                    opportunity.get(
                        "player_a_history_matches",
                        0,
                    )
                    or 0
                ),
                int(
                    opportunity.get(
                        "player_b_history_matches",
                        0,
                    )
                    or 0
                ),
            ),
            model_name=str(
                opportunity.get(
                    "model_name",
                    ACTIVE_PREDICTION_MODEL_NAME,
                )
                or ACTIVE_PREDICTION_MODEL_NAME
            ),
            ready=False,
            reason=(
                "Prediction opportunity exists but does not contain a "
                "usable model probability."
            ),
        )

    probability_b = (
        1.0
        - probability_a
    )

    confidence = _probability(
        opportunity.get(
            "model_confidence"
        )
    )

    history_a = int(
        opportunity.get(
            "player_a_history_matches",
            0,
        )
        or 0
    )

    history_b = int(
        opportunity.get(
            "player_b_history_matches",
            0,
        )
        or 0
    )

    minimum_history = min(
        history_a,
        history_b,
    )

    return FixturePrediction(
        fixture_id=int(
            fixture.id
        ),
        player_a=fixture.player_a,
        player_b=fixture.player_b,
        player_a_probability=probability_a,
        player_b_probability=probability_b,
        player_a_fair_odds=_fair_odds(
            probability_a
        ),
        player_b_fair_odds=_fair_odds(
            probability_b
        ),
        model_confidence=confidence,
        player_a_history_matches=history_a,
        player_b_history_matches=history_b,
        minimum_history_matches=minimum_history,
        model_name=str(
            opportunity.get(
                "model_name",
                ACTIVE_PREDICTION_MODEL_NAME,
            )
            or ACTIVE_PREDICTION_MODEL_NAME
        ),
        ready=True,
        reason="Prediction probability resolved.",
    )
