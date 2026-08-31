from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.services.model_performance_lab_service import (
    build_model_performance_lab,
)
from app.services.model_trust_service import (
    build_model_trust_report,
)
from app.services.portfolio_health_service import (
    build_portfolio_health,
)
from app.prediction_config import (
    ACTIVE_PREDICTION_MODEL_NAME,
)
from app.services.strategy_analytics_service import (
    analytics as build_strategy_analytics,
)


@dataclass(frozen=True)
class ModelHealthReport:
    model_name: str
    model_version: str

    health_score: int
    health_grade: str
    recommendation: str

    settled_predictions: int
    sample_ready: bool

    accuracy_percent: Optional[float]
    recent_accuracy_percent: Optional[float]
    prior_accuracy_percent: Optional[float]
    accuracy_drift_points: Optional[float]

    brier_score: Optional[float]
    calibration_error: Optional[float]

    trust_score: Optional[int]
    trust_grade: Optional[str]

    strategy_roi_percent: Optional[float]
    strategy_profit_loss: Optional[float]
    maximum_drawdown: Optional[float]

    portfolio_roi_percent: Optional[float]
    portfolio_profit_loss: Optional[float]

    accuracy_health: float
    calibration_health: float
    trust_health: float
    drift_health: float
    sample_health: float
    trading_health: float

    positive_findings: tuple[str, ...]
    warnings: tuple[str, ...]


def _number(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _percent(
    value: Any,
) -> Optional[float]:
    numeric = _number(value)

    if numeric is None:
        return None

    if -1.0 <= numeric <= 1.0:
        numeric *= 100.0

    return round(
        numeric,
        2,
    )


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


def _scale(
    value: Optional[float],
    *,
    poor: float,
    strong: float,
    higher_is_better: bool = True,
    unavailable: float = 50.0,
) -> float:
    if value is None:
        return float(unavailable)

    numeric = float(value)

    if strong == poor:
        return 100.0

    if higher_is_better:
        proportion = (
            numeric - poor
        ) / (
            strong - poor
        )
    else:
        proportion = (
            poor - numeric
        ) / (
            poor - strong
        )

    return round(
        _clamp(
            proportion,
            0.0,
            1.0,
        )
        * 100.0,
        2,
    )


def _sample_health(
    settled: int,
    minimum_sample: int,
) -> float:
    count = max(
        int(settled),
        0,
    )

    minimum = max(
        int(minimum_sample),
        1,
    )

    if count >= 500:
        return 100.0

    if count >= 250:
        return 90.0

    if count >= 100:
        return 80.0

    if count >= 50:
        return 65.0

    if count >= minimum:
        return 50.0

    return round(
        count
        / minimum
        * 40.0,
        2,
    )


def _health_grade(
    score: int,
) -> str:
    if score >= 85:
        return "Excellent"

    if score >= 70:
        return "Healthy"

    if score >= 55:
        return "Watch"

    if score >= 40:
        return "Weak"

    return "Critical"


def _recommendation(
    *,
    score: int,
    sample_ready: bool,
    accuracy_drift: Optional[float],
) -> str:
    if not sample_ready:
        return "Collect more settled predictions"

    if (
        accuracy_drift is not None
        and accuracy_drift <= -10.0
    ):
        return "Investigate recent performance deterioration"

    if score >= 85:
        return "Production ready"

    if score >= 70:
        return "Continue monitoring"

    if score >= 55:
        return "Use with caution"

    return "Do not promote"


def _intelligence_metrics(
    performance: dict,
) -> dict:
    leaderboard = (
        performance.get(
            "leaderboard"
        )
        or []
    )

    for row in leaderboard:
        if row.get("name") == "Player Intelligence":
            return row

    return (
        leaderboard[0]
        if leaderboard
        else {}
    )


def _top_strategy_metric(
    strategy_report: dict,
):
    metrics = (
        strategy_report.get(
            "metrics"
        )
        or []
    )

    if not metrics:
        return None

    return metrics[0]


def build_model_health(
    db,
    *,
    model_name: str = ACTIVE_PREDICTION_MODEL_NAME,
    trust_offset: int = 500,
    trust_limit: int = 3000,
    performance_builder: Callable = (
        build_model_performance_lab
    ),
    trust_builder: Callable = (
        build_model_trust_report
    ),
    strategy_builder: Callable = (
        build_strategy_analytics
    ),
    portfolio_builder: Callable = (
        build_portfolio_health
    ),
) -> ModelHealthReport:
    performance = (
        performance_builder(
            db
        )
    )

    try:
        trust = trust_builder(
            db,
            model_name=model_name,
            offset=trust_offset,
            limit=trust_limit,
        )
    except Exception:
        trust = None

    try:
        strategy = strategy_builder(
            db
        )
    except Exception:
        strategy = {
            "metrics": [],
        }

    try:
        portfolio = portfolio_builder(
            db
        )
    except Exception:
        portfolio = {}

    intelligence = (
        _intelligence_metrics(
            performance
        )
    )

    settled = int(
        performance.get(
            "settled_count",
            intelligence.get(
                "settled",
                0,
            ),
        )
        or 0
    )

    minimum_sample = int(
        performance.get(
            "minimum_sample",
            25,
        )
        or 25
    )

    sample_ready = bool(
        performance.get(
            "sample_ready",
            settled >= minimum_sample,
        )
    )

    accuracy = _percent(
        intelligence.get(
            "accuracy"
        )
    )

    recent = (
        performance.get(
            "recent_metrics"
        )
        or {}
    )

    prior = (
        performance.get(
            "prior_metrics"
        )
        or {}
    )

    recent_accuracy = _percent(
        recent.get(
            "accuracy"
        )
    )

    prior_accuracy = _percent(
        prior.get(
            "accuracy"
        )
    )

    accuracy_drift = _percent(
        performance.get(
            "accuracy_drift"
        )
    )

    brier = _number(
        intelligence.get(
            "brier"
        )
    )

    calibration = _number(
        intelligence.get(
            "calibration_error"
        )
    )

    trust_score = (
        int(
            trust.trust_score
        )
        if trust is not None
        else None
    )

    trust_grade = (
        trust.trust_grade
        if trust is not None
        else None
    )

    strategy_metric = (
        _top_strategy_metric(
            strategy
        )
    )

    strategy_roi = (
        _number(
            strategy_metric
            .roi_percent
        )
        if strategy_metric
        is not None
        else None
    )

    strategy_profit = (
        _number(
            strategy_metric
            .profit_loss
        )
        if strategy_metric
        is not None
        else None
    )

    maximum_drawdown = (
        _number(
            strategy_metric
            .maximum_drawdown
        )
        if strategy_metric
        is not None
        else None
    )

    portfolio_roi = _number(
        portfolio.get(
            "roi"
        )
    )

    portfolio_profit = _number(
        portfolio.get(
            "total_profit_loss"
        )
    )

    accuracy_health = _scale(
        accuracy,
        poor=48.0,
        strong=65.0,
    )

    brier_health = _scale(
        brier,
        poor=0.35,
        strong=0.20,
        higher_is_better=False,
    )

    calibration_health = _scale(
        calibration,
        poor=0.15,
        strong=0.03,
        higher_is_better=False,
    )

    probability_health = round(
        brier_health * 0.60
        + calibration_health * 0.40,
        2,
    )

    trust_health = (
        float(trust_score)
        if trust_score is not None
        else 50.0
    )

    if accuracy_drift is None:
        drift_health = 50.0
    elif accuracy_drift >= 5.0:
        drift_health = 100.0
    elif accuracy_drift >= 0.0:
        drift_health = 80.0
    elif accuracy_drift >= -5.0:
        drift_health = 60.0
    elif accuracy_drift >= -10.0:
        drift_health = 35.0
    else:
        drift_health = 10.0

    sample_health = _sample_health(
        settled,
        minimum_sample,
    )

    settled_strategy_decisions = int(
        strategy.get(
            "settled_decisions",
            0,
        )
        or 0
    )

    # Only strategy results are sufficiently linked to the decision engine
    # to influence model health. Portfolio ROI is displayed for context but
    # must not inflate model health until it is reliably linked to a model
    # version and settled prediction audit.
    trading_roi = (
        strategy_roi
        if (
            strategy_roi is not None
            and settled_strategy_decisions > 0
        )
        else None
    )

    trading_health = _scale(
        trading_roi,
        poor=-10.0,
        strong=15.0,
        unavailable=50.0,
    )

    weighted = (
        accuracy_health * 0.25
        + probability_health * 0.20
        + trust_health * 0.20
        + drift_health * 0.10
        + sample_health * 0.15
        + trading_health * 0.10
    )

    if not sample_ready:
        weighted = min(
            weighted,
            64.0,
        )

    health_score = int(
        round(
            _clamp(
                weighted
            )
        )
    )

    positives: list[str] = []
    warnings: list[str] = []

    if accuracy is not None:
        if accuracy >= 58.0:
            positives.append(
                "Settled prediction accuracy is healthy."
            )
        elif accuracy < 52.0:
            warnings.append(
                "Settled prediction accuracy is weak."
            )

    if brier is not None:
        if brier <= 0.26:
            positives.append(
                "Brier score indicates good probability quality."
            )
        elif brier > 0.30:
            warnings.append(
                "Brier score indicates poor probability quality."
            )

    if calibration is not None:
        if calibration <= 0.06:
            positives.append(
                "Prediction confidence is well calibrated."
            )
        elif calibration > 0.12:
            warnings.append(
                "Prediction confidence is materially miscalibrated."
            )

    if trust_score is not None:
        if trust_score >= 70:
            positives.append(
                "Historical model trust is strong."
            )
        elif trust_score < 55:
            warnings.append(
                "Historical model trust is limited."
            )
    else:
        warnings.append(
            "Model Trust is unavailable."
        )

    if not sample_ready:
        warnings.append(
            "The settled prediction sample is not yet large enough."
        )

    if accuracy_drift is not None:
        if accuracy_drift > 0:
            positives.append(
                "Recent accuracy is improving."
            )
        elif accuracy_drift <= -10.0:
            warnings.append(
                "Recent accuracy has deteriorated sharply."
            )
        elif accuracy_drift < 0:
            warnings.append(
                "Recent accuracy is below the previous window."
            )

    if trading_roi is not None:
        if trading_roi > 0:
            positives.append(
                "Settled strategy ROI is positive."
            )
        elif trading_roi < 0:
            warnings.append(
                "Settled strategy ROI is negative."
            )
    else:
        warnings.append(
            "There are not enough settled strategy results for model-linked ROI."
        )

    if (
        portfolio_roi is not None
        and settled_strategy_decisions == 0
    ):
        warnings.append(
            "Portfolio ROI is shown for context but is not linked closely enough to this model version to affect health."
        )

    model_version = (
        trust.model_version
        if trust is not None
        else model_name
    )

    return ModelHealthReport(
        model_name=model_name,
        model_version=(
            model_version
        ),
        health_score=(
            health_score
        ),
        health_grade=(
            _health_grade(
                health_score
            )
        ),
        recommendation=(
            _recommendation(
                score=health_score,
                sample_ready=(
                    sample_ready
                ),
                accuracy_drift=(
                    accuracy_drift
                ),
            )
        ),
        settled_predictions=settled,
        sample_ready=(
            sample_ready
        ),
        accuracy_percent=accuracy,
        recent_accuracy_percent=(
            recent_accuracy
        ),
        prior_accuracy_percent=(
            prior_accuracy
        ),
        accuracy_drift_points=(
            accuracy_drift
        ),
        brier_score=brier,
        calibration_error=(
            calibration
        ),
        trust_score=trust_score,
        trust_grade=trust_grade,
        strategy_roi_percent=(
            strategy_roi
        ),
        strategy_profit_loss=(
            strategy_profit
        ),
        maximum_drawdown=(
            maximum_drawdown
        ),
        portfolio_roi_percent=(
            portfolio_roi
        ),
        portfolio_profit_loss=(
            portfolio_profit
        ),
        accuracy_health=(
            accuracy_health
        ),
        calibration_health=(
            probability_health
        ),
        trust_health=(
            trust_health
        ),
        drift_health=(
            drift_health
        ),
        sample_health=(
            sample_health
        ),
        trading_health=(
            trading_health
        ),
        positive_findings=tuple(
            positives
        ),
        warnings=tuple(
            warnings
        ),
    )


def model_health_summary(
    report: ModelHealthReport,
) -> dict:
    return {
        "model_name": (
            report.model_name
        ),
        "model_version": (
            report.model_version
        ),
        "health_score": (
            report.health_score
        ),
        "health_grade": (
            report.health_grade
        ),
        "recommendation": (
            report.recommendation
        ),
        "settled_predictions": (
            report.settled_predictions
        ),
        "sample_ready": (
            report.sample_ready
        ),
        "accuracy_percent": (
            report.accuracy_percent
        ),
        "recent_accuracy_percent": (
            report
            .recent_accuracy_percent
        ),
        "prior_accuracy_percent": (
            report
            .prior_accuracy_percent
        ),
        "accuracy_drift_points": (
            report
            .accuracy_drift_points
        ),
        "brier_score": (
            report.brier_score
        ),
        "calibration_error": (
            report.calibration_error
        ),
        "trust_score": (
            report.trust_score
        ),
        "trust_grade": (
            report.trust_grade
        ),
        "strategy_roi_percent": (
            report
            .strategy_roi_percent
        ),
        "strategy_profit_loss": (
            report
            .strategy_profit_loss
        ),
        "maximum_drawdown": (
            report.maximum_drawdown
        ),
        "portfolio_roi_percent": (
            report
            .portfolio_roi_percent
        ),
        "portfolio_profit_loss": (
            report
            .portfolio_profit_loss
        ),
        "components": {
            "accuracy": (
                report.accuracy_health
            ),
            "calibration": (
                report
                .calibration_health
            ),
            "trust": (
                report.trust_health
            ),
            "drift": (
                report.drift_health
            ),
            "sample": (
                report.sample_health
            ),
            "trading": (
                report.trading_health
            ),
        },
        "positive_findings": list(
            report.positive_findings
        ),
        "warnings": list(
            report.warnings
        ),
    }
