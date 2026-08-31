from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.services.advanced_historical_snapshot_engine import (
    AdvancedHistoricalSnapshotEngine,
)
from app.services.prediction_model_registry import (
    PredictionModelRegistry,
    prediction_model_registry,
)
from app.prediction_config import (
    ACTIVE_PREDICTION_MODEL_NAME,
)


DEFAULT_MODEL_NAME = ACTIVE_PREDICTION_MODEL_NAME


@dataclass(frozen=True)
class PredictionContext:
    match_id: int

    player_a_name: str
    player_b_name: str

    model_name: str
    model_version: str

    player_a_probability: float
    player_b_probability: float
    predicted_winner: str
    model_confidence: float
    model_score: float

    player_a_history_matches: int
    player_b_history_matches: int

    explanations: tuple[str, ...]
    contributions: tuple[dict, ...]

    snapshot: object
    prediction: object


def _contribution_payload(
    prediction,
) -> tuple[dict, ...]:
    payload = []

    for item in prediction.contributions:
        weighted_score = float(
            item.weighted_score
        )

        payload.append({
            "feature": item.feature_name,
            "label": (
                str(item.feature_name)
                .replace("_", " ")
                .title()
            ),
            "raw_edge": float(
                item.raw_edge
            ),
            "normalised_edge": float(
                item.normalised_edge
            ),
            "weight": float(
                item.weight
            ),
            "weighted_score": (
                weighted_score
            ),
            "direction": (
                "player_a"
                if weighted_score > 0
                else (
                    "player_b"
                    if weighted_score < 0
                    else "neutral"
                )
            ),
            "impact_percent": round(
                min(
                    abs(weighted_score)
                    * 1000.0,
                    100.0,
                ),
                1,
            ),
            "confidence": float(
                item.confidence
            ),
            "explanation": (
                item.explanation
            ),
        })

    return tuple(
        sorted(
            payload,
            key=lambda row: abs(
                row["weighted_score"]
            ),
            reverse=True,
        )
    )


def build_prediction_context(
    db,
    match_id: int,
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    competition_code: Optional[str] = None,
    snapshot_engine: Optional[
        AdvancedHistoricalSnapshotEngine
    ] = None,
    model_registry: Optional[
        PredictionModelRegistry
    ] = None,
) -> PredictionContext:
    snapshots = (
        snapshot_engine
        or AdvancedHistoricalSnapshotEngine()
    )

    registry = (
        model_registry
        or prediction_model_registry
    )

    registered = registry.get_registered(
        model_name
    )

    if competition_code is None:
        snapshot = (
            snapshots
            .build_match_snapshot(
                db,
                int(match_id),
            )
        )
    else:
        snapshot = (
            snapshots
            .build_match_snapshot(
                db,
                int(match_id),
                competition_code=(
                    competition_code
                ),
            )
        )

    prediction = (
        registered.model.predict(
            snapshot
        )
    )

    player_a_history = int(
        getattr(
            snapshot.player_a
            .advanced_features,
            "matches_available",
            0,
        )
        or 0
    )

    player_b_history = int(
        getattr(
            snapshot.player_b
            .advanced_features,
            "matches_available",
            0,
        )
        or 0
    )

    return PredictionContext(
        match_id=int(
            snapshot.match_id
        ),
        player_a_name=(
            prediction.player_a_name
        ),
        player_b_name=(
            prediction.player_b_name
        ),
        model_name=(
            registered.name
        ),
        model_version=(
            registered.version
        ),
        player_a_probability=float(
            prediction
            .player_a_probability
        ),
        player_b_probability=float(
            prediction
            .player_b_probability
        ),
        predicted_winner=(
            prediction.predicted_winner
        ),
        model_confidence=float(
            prediction.confidence
        ),
        model_score=float(
            prediction.model_score
        ),
        player_a_history_matches=(
            player_a_history
        ),
        player_b_history_matches=(
            player_b_history
        ),
        explanations=tuple(
            prediction.explanation
        ),
        contributions=(
            _contribution_payload(
                prediction
            )
        ),
        snapshot=snapshot,
        prediction=prediction,
    )


def context_to_opportunity(
    context: PredictionContext,
    *,
    fixture_date=None,
    tournament=None,
) -> dict:
    probability = max(
        context.player_a_probability,
        context.player_b_probability,
    )

    fair_odds = (
        round(
            100.0 / probability,
            2,
        )
        if probability > 0
        else None
    )

    selection = (
        context.player_a_name
        if (
            context.player_a_probability
            >= context.player_b_probability
        )
        else context.player_b_name
    )

    return {
        "match_id": context.match_id,
        "date": fixture_date,
        "tournament": tournament,
        "player_a": (
            context.player_a_name
        ),
        "player_b": (
            context.player_b_name
        ),
        "selection": selection,
        "probability": round(
            probability,
            1,
        ),
        "fair_odds": fair_odds,
        "model_name": (
            context.model_name
        ),
        "model_version": (
            context.model_version
        ),
        "player_a_probability": round(
            context.player_a_probability,
            3,
        ),
        "player_b_probability": round(
            context.player_b_probability,
            3,
        ),
        "model_confidence": (
            context.model_confidence
        ),
        "model_score": (
            context.model_score
        ),
        "player_a_history_matches": (
            context
            .player_a_history_matches
        ),
        "player_b_history_matches": (
            context
            .player_b_history_matches
        ),
        "explanations": list(
            context.explanations
        ),
        "contributions": [
            dict(item)
            for item in context.contributions
        ],
    }


def context_summary(
    context: PredictionContext,
) -> dict:
    return {
        "match_id": (
            context.match_id
        ),
        "player_a_name": (
            context.player_a_name
        ),
        "player_b_name": (
            context.player_b_name
        ),
        "model_name": (
            context.model_name
        ),
        "model_version": (
            context.model_version
        ),
        "player_a_probability": (
            context
            .player_a_probability
        ),
        "player_b_probability": (
            context
            .player_b_probability
        ),
        "predicted_winner": (
            context.predicted_winner
        ),
        "model_confidence": (
            context.model_confidence
        ),
        "model_score": (
            context.model_score
        ),
        "player_a_history_matches": (
            context
            .player_a_history_matches
        ),
        "player_b_history_matches": (
            context
            .player_b_history_matches
        ),
        "explanations": list(
            context.explanations
        ),
        "contributions": [
            dict(item)
            for item in context.contributions
        ],
    }
