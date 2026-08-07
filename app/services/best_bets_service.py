from __future__ import annotations

from math import ceil
from typing import Optional

from app.models.match import Match
from app.services.advanced_historical_snapshot_engine import (
    AdvancedHistoricalSnapshotEngine,
)
from app.services.prediction_context_service import (
    build_prediction_context,
    context_to_opportunity,
)
from app.services.prediction_model_registry import (
    PredictionModelRegistry,
    prediction_model_registry,
)


RESEARCH_MODEL_NAME = "transparent-v3.3"
MINIMUM_HISTORY_MATCHES = 5


def _confidence_label(
    probability: float,
) -> tuple[str, int]:
    """
    Preserve the confidence labels expected by existing screens.

    Probability is expressed as a percentage from 0 to 100.
    """
    if probability >= 70.0:
        return "High", 5

    if probability >= 62.0:
        return "Good", 4

    if probability >= 55.0:
        return "Moderate", 3

    return "Low", 2


def _minimum_odds(
    fair_odds: float,
) -> float:
    """
    Require a 5% price premium over the model's fair odds.

    Ceiling prevents displaying a threshold fractionally below the
    intended two-decimal price.
    """
    return (
        ceil(
            float(fair_odds)
            * 1.05
            * 100.0
        )
        / 100.0
    )


def build_best_bets(
    db,
    limit: int = 5,
    *,
    model_name: str = RESEARCH_MODEL_NAME,
    snapshot_engine: Optional[
        AdvancedHistoricalSnapshotEngine
    ] = None,
    model_registry: Optional[
        PredictionModelRegistry
    ] = None,
):
    """
    Build match-winner opportunities using the shared Prediction Context.

    The existing public dictionary contract is preserved for Prediction
    Centre, Daily Briefing, opportunity ranking and older callers.
    """
    safe_limit = max(
        1,
        min(
            int(limit),
            500,
        ),
    )

    snapshots = (
        snapshot_engine
        or AdvancedHistoricalSnapshotEngine()
    )

    registry = (
        model_registry
        or prediction_model_registry
    )

    scheduled_matches = (
        db.query(Match)
        .filter(
            Match.status == "scheduled"
        )
        .order_by(
            Match.date.asc(),
            Match.id.asc(),
        )
        .all()
    )

    best_bets = []

    for match in scheduled_matches:
        try:
            context = build_prediction_context(
                db,
                match.id,
                model_name=model_name,
                snapshot_engine=snapshots,
                model_registry=registry,
            )
        except (
            LookupError,
            RuntimeError,
            TypeError,
            ValueError,
        ):
            # A fixture with insufficient or unresolved history should not
            # prevent all other scheduled opportunities from being built.
            continue

        if (
            context.player_a_history_matches
            < MINIMUM_HISTORY_MATCHES
            or context.player_b_history_matches
            < MINIMUM_HISTORY_MATCHES
        ):
            continue

        opportunity = context_to_opportunity(
            context,
            fixture_date=match.date,
            tournament=match.tournament,
        )

        probability = float(
            opportunity["probability"]
        )

        if probability <= 0:
            continue

        fair_odds = float(
            opportunity["fair_odds"]
        )

        confidence, stars = (
            _confidence_label(
                probability
            )
        )

        opportunity.update({
            "confidence": confidence,
            "stars": stars,
            "minimum_odds": (
                _minimum_odds(
                    fair_odds
                )
            ),
        })

        best_bets.append(
            opportunity
        )

    best_bets.sort(
        key=lambda bet: (
            bet["stars"],
            bet["probability"],
            bet["model_confidence"],
        ),
        reverse=True,
    )

    return best_bets[:safe_limit]
