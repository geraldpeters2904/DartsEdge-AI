from __future__ import annotations

from dataclasses import dataclass, replace
from statistics import mean, pstdev
from typing import Iterable, Optional

from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


@dataclass(frozen=True)
class StabilityScenarioResult:
    scenario: str
    feature: str
    direction: str
    player_a_probability: float
    predicted_winner: str
    probability_change: float


@dataclass(frozen=True)
class FeatureSensitivity:
    feature: str
    negative_probability: float
    positive_probability: float
    probability_span: float
    maximum_absolute_change: float
    winner_changed: bool


@dataclass(frozen=True)
class PredictionStabilityReport:
    match_id: int
    model_version: str
    player_a_name: str
    player_b_name: str

    base_probability: float
    base_winner: str

    simulation_count: int
    mean_probability: float
    minimum_probability: float
    maximum_probability: float
    probability_range: float
    standard_deviation: float

    winner_change_count: int
    stability_score: int
    stability_grade: str

    most_sensitive_feature: Optional[str]
    scenarios: tuple[StabilityScenarioResult, ...]
    sensitivities: tuple[FeatureSensitivity, ...]

    positive_reasons: tuple[str, ...]
    caution_reasons: tuple[str, ...]


DEFAULT_PERTURBATIONS = {
    "overall_rating": 5.0,
    "scoring_rating": 8.0,
    "finishing_rating": 8.0,
    "maximums_rating": 8.0,
    "form_rating": 8.0,
}


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return min(
        max(
            float(value),
            minimum,
        ),
        maximum,
    )


def _grade(
    score: int,
) -> str:
    if score >= 90:
        return "Excellent"

    if score >= 80:
        return "Strong"

    if score >= 65:
        return "Moderate"

    if score >= 50:
        return "Fragile"

    return "Unstable"


def _perturb_snapshot(
    snapshot,
    *,
    feature_name: str,
    delta: float,
):
    player_a = replace(
        snapshot.player_a,
        **{
            feature_name: (
                float(
                    getattr(
                        snapshot.player_a,
                        feature_name,
                    )
                )
                + float(delta)
            )
        },
    )

    player_b = replace(
        snapshot.player_b,
        **{
            feature_name: (
                float(
                    getattr(
                        snapshot.player_b,
                        feature_name,
                    )
                )
                - float(delta)
            )
        },
    )

    return replace(
        snapshot,
        player_a=player_a,
        player_b=player_b,
    )


def _stability_score(
    *,
    probability_range: float,
    standard_deviation: float,
    winner_change_count: int,
    simulation_count: int,
) -> int:
    range_penalty = min(
        probability_range * 4.0,
        40.0,
    )

    deviation_penalty = min(
        standard_deviation * 8.0,
        30.0,
    )

    winner_penalty = (
        (
            winner_change_count
            / simulation_count
        )
        * 30.0
        if simulation_count
        else 0.0
    )

    return int(
        round(
            _clamp(
                100.0
                - range_penalty
                - deviation_penalty
                - winner_penalty
            )
        )
    )


def analyse_snapshot_stability(
    snapshot,
    *,
    prediction_engine: Optional[
        TransparentPredictionEngineV33
    ] = None,
    perturbations: Optional[
        dict[str, float]
    ] = None,
) -> PredictionStabilityReport:
    engine = (
        prediction_engine
        or TransparentPredictionEngineV33()
    )

    changes = dict(
        perturbations
        or DEFAULT_PERTURBATIONS
    )

    base = engine.predict(
        snapshot
    )

    scenario_results: list[
        StabilityScenarioResult
    ] = []

    sensitivity_rows: list[
        FeatureSensitivity
    ] = []

    for feature_name, amount in changes.items():
        negative_snapshot = _perturb_snapshot(
            snapshot,
            feature_name=feature_name,
            delta=-float(amount),
        )

        positive_snapshot = _perturb_snapshot(
            snapshot,
            feature_name=feature_name,
            delta=float(amount),
        )

        negative_prediction = engine.predict(
            negative_snapshot
        )
        positive_prediction = engine.predict(
            positive_snapshot
        )

        negative_probability = float(
            negative_prediction
            .player_a_probability
        )

        positive_probability = float(
            positive_prediction
            .player_a_probability
        )

        for direction, prediction in (
            (
                "negative",
                negative_prediction,
            ),
            (
                "positive",
                positive_prediction,
            ),
        ):
            probability = float(
                prediction
                .player_a_probability
            )

            scenario_results.append(
                StabilityScenarioResult(
                    scenario=(
                        f"{feature_name}:"
                        f"{direction}"
                    ),
                    feature=feature_name,
                    direction=direction,
                    player_a_probability=(
                        probability
                    ),
                    predicted_winner=(
                        prediction
                        .predicted_winner
                    ),
                    probability_change=round(
                        probability
                        - float(
                            base
                            .player_a_probability
                        ),
                        3,
                    ),
                )
            )

        sensitivity_rows.append(
            FeatureSensitivity(
                feature=feature_name,
                negative_probability=(
                    negative_probability
                ),
                positive_probability=(
                    positive_probability
                ),
                probability_span=round(
                    abs(
                        positive_probability
                        - negative_probability
                    ),
                    3,
                ),
                maximum_absolute_change=round(
                    max(
                        abs(
                            negative_probability
                            - float(
                                base
                                .player_a_probability
                            )
                        ),
                        abs(
                            positive_probability
                            - float(
                                base
                                .player_a_probability
                            )
                        ),
                    ),
                    3,
                ),
                winner_changed=(
                    negative_prediction
                    .predicted_winner
                    != base.predicted_winner
                    or positive_prediction
                    .predicted_winner
                    != base.predicted_winner
                ),
            )
        )

    probabilities = [
        float(
            base.player_a_probability
        ),
        *[
            item.player_a_probability
            for item in scenario_results
        ],
    ]

    winner_change_count = sum(
        item.predicted_winner
        != base.predicted_winner
        for item in scenario_results
    )

    probability_range = (
        max(probabilities)
        - min(probabilities)
    )

    standard_deviation = pstdev(
        probabilities
    )

    score = _stability_score(
        probability_range=(
            probability_range
        ),
        standard_deviation=(
            standard_deviation
        ),
        winner_change_count=(
            winner_change_count
        ),
        simulation_count=len(
            scenario_results
        ),
    )

    ordered_sensitivities = tuple(
        sorted(
            sensitivity_rows,
            key=lambda item: (
                item.maximum_absolute_change,
                item.probability_span,
            ),
            reverse=True,
        )
    )

    positives: list[str] = []
    cautions: list[str] = []

    if winner_change_count == 0:
        positives.append(
            "All perturbation scenarios selected the same winner."
        )
    else:
        cautions.append(
            f"The predicted winner changed in "
            f"{winner_change_count} scenario(s)."
        )

    if probability_range <= 2.0:
        positives.append(
            "The prediction moved by no more than two percentage points."
        )
    elif probability_range >= 8.0:
        cautions.append(
            "The probability range is wide under small input changes."
        )

    if standard_deviation <= 0.75:
        positives.append(
            "Probability variance is low."
        )
    elif standard_deviation >= 2.5:
        cautions.append(
            "Probability variance is high."
        )

    most_sensitive = (
        ordered_sensitivities[0]
        if ordered_sensitivities
        else None
    )

    if (
        most_sensitive is not None
        and most_sensitive
        .maximum_absolute_change
        >= 3.0
    ):
        cautions.append(
            "The prediction is particularly sensitive to "
            f"{most_sensitive.feature.replace('_', ' ')}."
        )

    return PredictionStabilityReport(
        match_id=int(
            snapshot.match_id
        ),
        model_version=(
            base.model_version
        ),
        player_a_name=(
            base.player_a_name
        ),
        player_b_name=(
            base.player_b_name
        ),
        base_probability=float(
            base.player_a_probability
        ),
        base_winner=(
            base.predicted_winner
        ),
        simulation_count=len(
            scenario_results
        ),
        mean_probability=round(
            mean(probabilities),
            3,
        ),
        minimum_probability=round(
            min(probabilities),
            3,
        ),
        maximum_probability=round(
            max(probabilities),
            3,
        ),
        probability_range=round(
            probability_range,
            3,
        ),
        standard_deviation=round(
            standard_deviation,
            3,
        ),
        winner_change_count=(
            winner_change_count
        ),
        stability_score=score,
        stability_grade=_grade(
            score
        ),
        most_sensitive_feature=(
            most_sensitive.feature
            if most_sensitive
            else None
        ),
        scenarios=tuple(
            scenario_results
        ),
        sensitivities=(
            ordered_sensitivities
        ),
        positive_reasons=tuple(
            positives
        ),
        caution_reasons=tuple(
            cautions
        ),
    )


def build_match_stability_report(
    db,
    match_id: int,
    *,
    snapshot_engine=None,
    prediction_engine=None,
    competition_code=None,
    perturbations=None,
) -> PredictionStabilityReport:
    if snapshot_engine is None:
        from app.services.advanced_historical_snapshot_engine import (
            AdvancedHistoricalSnapshotEngine,
        )

        snapshot_engine = (
            AdvancedHistoricalSnapshotEngine()
        )

    snapshot = (
        snapshot_engine
        .build_match_snapshot(
            db,
            int(match_id),
            competition_code=(
                competition_code
            ),
        )
    )

    return analyse_snapshot_stability(
        snapshot,
        prediction_engine=(
            prediction_engine
        ),
        perturbations=(
            perturbations
        ),
    )


def stability_summary(
    report: PredictionStabilityReport,
) -> dict:
    return {
        "match_id": report.match_id,
        "model_version": (
            report.model_version
        ),
        "player_a_name": (
            report.player_a_name
        ),
        "player_b_name": (
            report.player_b_name
        ),
        "base_probability": (
            report.base_probability
        ),
        "base_winner": (
            report.base_winner
        ),
        "simulation_count": (
            report.simulation_count
        ),
        "mean_probability": (
            report.mean_probability
        ),
        "minimum_probability": (
            report.minimum_probability
        ),
        "maximum_probability": (
            report.maximum_probability
        ),
        "probability_range": (
            report.probability_range
        ),
        "standard_deviation": (
            report.standard_deviation
        ),
        "winner_change_count": (
            report.winner_change_count
        ),
        "stability_score": (
            report.stability_score
        ),
        "stability_grade": (
            report.stability_grade
        ),
        "most_sensitive_feature": (
            report.most_sensitive_feature
        ),
        "positive_reasons": list(
            report.positive_reasons
        ),
        "caution_reasons": list(
            report.caution_reasons
        ),
        "sensitivities": [
            {
                "feature": item.feature,
                "negative_probability": (
                    item.negative_probability
                ),
                "positive_probability": (
                    item.positive_probability
                ),
                "probability_span": (
                    item.probability_span
                ),
                "maximum_absolute_change": (
                    item.maximum_absolute_change
                ),
                "winner_changed": (
                    item.winner_changed
                ),
            }
            for item in report.sensitivities
        ],
    }
