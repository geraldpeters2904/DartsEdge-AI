from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from app.services.model_performance_laboratory import (
    ModelPerformanceLaboratory,
    ModelPerformanceSummary,
)
from app.services.model_segment_laboratory import (
    ModelSegmentLaboratory,
    ModelSegmentSummary,
)
from app.services.prediction_model_registry import (
    PredictionModelRegistry,
    prediction_model_registry,
)
from app.prediction_config import (
    ACTIVE_PREDICTION_MODEL_NAME,
)


@dataclass(frozen=True)
class ModelTrustReport:
    model_name: str
    model_version: str

    trust_score: int
    trust_grade: str

    sample_size: int
    accuracy: Optional[float]
    average_brier_score: Optional[float]
    average_log_loss: Optional[float]

    accuracy_score: float
    calibration_score: float
    probability_quality_score: float
    sample_size_score: float
    confidence_reliability_score: float
    stage_reliability_score: float

    strongest_confidence_band: Optional[str]
    weakest_confidence_band: Optional[str]
    strongest_stage: Optional[str]
    weakest_stage: Optional[str]

    positive_reasons: tuple[str, ...]
    caution_reasons: tuple[str, ...]


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
) -> float:
    if value is None:
        return 0.0

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


def _sample_score(
    sample_size: int,
) -> float:
    size = max(
        int(sample_size),
        0,
    )

    if size >= 3000:
        return 100.0

    if size >= 1500:
        return 90.0

    if size >= 750:
        return 80.0

    if size >= 300:
        return 65.0

    if size >= 100:
        return 45.0

    if size >= 25:
        return 25.0

    return round(
        size / 25.0 * 25.0,
        2,
    )


def _calibration_score(
    summary: ModelPerformanceSummary,
) -> float:
    """
    Use Brier and log-loss quality as the current calibration proxy.

    The validation engine already calculates calibration buckets, but the
    performance summary intentionally exposes only aggregate metrics.
    """
    brier = _scale(
        summary.average_brier_score,
        poor=0.35,
        strong=0.20,
        higher_is_better=False,
    )

    log_loss = _scale(
        summary.average_log_loss,
        poor=0.95,
        strong=0.60,
        higher_is_better=False,
    )

    return round(
        brier * 0.60
        + log_loss * 0.40,
        2,
    )


def _probability_quality_score(
    summary: ModelPerformanceSummary,
) -> float:
    brier = _scale(
        summary.average_brier_score,
        poor=0.35,
        strong=0.20,
        higher_is_better=False,
    )

    log_loss = _scale(
        summary.average_log_loss,
        poor=0.95,
        strong=0.60,
        higher_is_better=False,
    )

    return round(
        brier * 0.50
        + log_loss * 0.50,
        2,
    )


def _segment_reliability(
    metrics: Sequence,
) -> float:
    available = [
        metric
        for metric in metrics
        if (
            metric.accuracy
            is not None
            and metric.predictions >= 25
        )
    ]

    if not available:
        return 0.0

    accuracies = [
        float(metric.accuracy)
        for metric in available
    ]

    spread = (
        max(accuracies)
        - min(accuracies)
    )

    spread_score = _scale(
        spread,
        poor=25.0,
        strong=5.0,
        higher_is_better=False,
    )

    average_accuracy = (
        sum(accuracies)
        / len(accuracies)
    )

    average_score = _scale(
        average_accuracy,
        poor=48.0,
        strong=65.0,
    )

    return round(
        spread_score * 0.55
        + average_score * 0.45,
        2,
    )


def _strongest_metric(
    metrics: Iterable,
):
    available = [
        metric
        for metric in metrics
        if metric.accuracy is not None
    ]

    if not available:
        return None

    return max(
        available,
        key=lambda item: (
            float(item.accuracy),
            int(item.predictions),
        ),
    )


def _weakest_metric(
    metrics: Iterable,
):
    available = [
        metric
        for metric in metrics
        if metric.accuracy is not None
    ]

    if not available:
        return None

    return min(
        available,
        key=lambda item: (
            float(item.accuracy),
            -int(item.predictions),
        ),
    )


def _trust_grade(
    score: int,
) -> str:
    if score >= 85:
        return "Very High"

    if score >= 70:
        return "High"

    if score >= 55:
        return "Moderate"

    if score >= 40:
        return "Low"

    return "Very Low"


def build_model_trust_report(
    db: Session,
    *,
    model_name: str = ACTIVE_PREDICTION_MODEL_NAME,
    offset: int = 0,
    limit: int = 3000,
    competition_code: Optional[str] = None,
    model_registry: Optional[
        PredictionModelRegistry
    ] = None,
    performance_laboratory: Optional[
        ModelPerformanceLaboratory
    ] = None,
    segment_laboratory: Optional[
        ModelSegmentLaboratory
    ] = None,
) -> ModelTrustReport:
    registry = (
        model_registry
        or prediction_model_registry
    )

    performance_lab = (
        performance_laboratory
        or ModelPerformanceLaboratory(
            model_registry=registry
        )
    )

    segment_lab = (
        segment_laboratory
        or ModelSegmentLaboratory(
            model_registry=registry
        )
    )

    registered = registry.get_registered(
        model_name
    )

    selected_ids = (
        db.query(
            __import__(
                "app.models.match",
                fromlist=["Match"],
            ).Match.id
        )
        .filter(
            __import__(
                "app.models.match",
                fromlist=["Match"],
            ).Match.status
            == "completed"
        )
        .order_by(
            __import__(
                "app.models.match",
                fromlist=["Match"],
            ).Match.date.asc(),
            __import__(
                "app.models.match",
                fromlist=["Match"],
            ).Match.id.asc(),
        )
        .offset(
            max(
                int(offset),
                0,
            )
        )
        .limit(
            max(
                int(limit),
                1,
            )
        )
        .all()
    )

    match_ids = [
        int(match_id)
        for (match_id,) in selected_ids
    ]

    performance = (
        performance_lab.evaluate_model(
            db,
            model_name=model_name,
            match_ids=match_ids,
            competition_code=(
                competition_code
            ),
        )
    )

    segments = (
        segment_lab.compare(
            db,
            model_names=(
                model_name,
            ),
            offset=max(
                int(offset),
                0,
            ),
            limit=max(
                int(limit),
                1,
            ),
            competition_code=(
                competition_code
            ),
        )
    )

    segment_summary = (
        segments.model_summaries[0]
        if segments.model_summaries
        else ModelSegmentSummary(
            model_name=registered.name,
            model_version=registered.version,
            matches_evaluated=0,
            favourite_bands=(),
            confidence_bands=(),
            stages=(),
        )
    )

    accuracy_score = _scale(
        performance.accuracy,
        poor=48.0,
        strong=65.0,
    )

    calibration_score = (
        _calibration_score(
            performance
        )
    )

    probability_quality_score = (
        _probability_quality_score(
            performance
        )
    )

    sample_size_score = (
        _sample_score(
            performance.matches_evaluated
        )
    )

    confidence_score = (
        _segment_reliability(
            segment_summary
            .confidence_bands
        )
    )

    stage_score = (
        _segment_reliability(
            segment_summary.stages
        )
    )

    weighted = (
        accuracy_score * 0.25
        + calibration_score * 0.20
        + probability_quality_score * 0.20
        + sample_size_score * 0.15
        + confidence_score * 0.10
        + stage_score * 0.10
    )

    trust_score = int(
        round(
            _clamp(
                weighted
            )
        )
    )

    strongest_confidence = (
        _strongest_metric(
            segment_summary
            .confidence_bands
        )
    )

    weakest_confidence = (
        _weakest_metric(
            segment_summary
            .confidence_bands
        )
    )

    strongest_stage = (
        _strongest_metric(
            segment_summary.stages
        )
    )

    weakest_stage = (
        _weakest_metric(
            segment_summary.stages
        )
    )

    positive: list[str] = []
    cautions: list[str] = []

    if performance.matches_evaluated >= 1000:
        positive.append(
            "Trust is supported by a large historical sample."
        )
    elif performance.matches_evaluated < 100:
        cautions.append(
            "The historical sample is too small for strong trust."
        )

    if (
        performance.accuracy
        is not None
        and performance.accuracy >= 58.0
    ):
        positive.append(
            "Historical accuracy is above the model baseline."
        )
    elif (
        performance.accuracy
        is not None
        and performance.accuracy < 52.0
    ):
        cautions.append(
            "Historical accuracy is weak."
        )

    if (
        performance.average_brier_score
        is not None
        and performance.average_brier_score
        <= 0.26
    ):
        positive.append(
            "Probability quality is strong by Brier score."
        )
    elif (
        performance.average_brier_score
        is not None
        and performance.average_brier_score
        > 0.30
    ):
        cautions.append(
            "Brier score indicates weak probability quality."
        )

    if calibration_score >= 70.0:
        positive.append(
            "The model is reasonably well calibrated."
        )
    elif calibration_score < 40.0:
        cautions.append(
            "Calibration quality needs improvement."
        )

    if confidence_score >= 70.0:
        positive.append(
            "Confidence bands are historically consistent."
        )
    elif confidence_score < 40.0:
        cautions.append(
            "Performance varies materially across confidence bands."
        )

    if stage_score >= 70.0:
        positive.append(
            "Performance is reasonably stable across stages."
        )
    elif stage_score < 40.0:
        cautions.append(
            "Performance varies materially by match stage."
        )

    return ModelTrustReport(
        model_name=registered.name,
        model_version=registered.version,
        trust_score=trust_score,
        trust_grade=_trust_grade(
            trust_score
        ),
        sample_size=(
            performance.matches_evaluated
        ),
        accuracy=performance.accuracy,
        average_brier_score=(
            performance.average_brier_score
        ),
        average_log_loss=(
            performance.average_log_loss
        ),
        accuracy_score=accuracy_score,
        calibration_score=(
            calibration_score
        ),
        probability_quality_score=(
            probability_quality_score
        ),
        sample_size_score=(
            sample_size_score
        ),
        confidence_reliability_score=(
            confidence_score
        ),
        stage_reliability_score=(
            stage_score
        ),
        strongest_confidence_band=(
            strongest_confidence
            .segment_label
            if strongest_confidence
            else None
        ),
        weakest_confidence_band=(
            weakest_confidence
            .segment_label
            if weakest_confidence
            else None
        ),
        strongest_stage=(
            strongest_stage
            .segment_label
            if strongest_stage
            else None
        ),
        weakest_stage=(
            weakest_stage
            .segment_label
            if weakest_stage
            else None
        ),
        positive_reasons=tuple(
            positive
        ),
        caution_reasons=tuple(
            cautions
        ),
    )


def trust_summary(
    report: ModelTrustReport,
) -> dict:
    return {
        "model_name": report.model_name,
        "model_version": (
            report.model_version
        ),
        "trust_score": (
            report.trust_score
        ),
        "trust_grade": (
            report.trust_grade
        ),
        "sample_size": (
            report.sample_size
        ),
        "accuracy": report.accuracy,
        "average_brier_score": (
            report.average_brier_score
        ),
        "average_log_loss": (
            report.average_log_loss
        ),
        "accuracy_score": (
            report.accuracy_score
        ),
        "calibration_score": (
            report.calibration_score
        ),
        "probability_quality_score": (
            report.probability_quality_score
        ),
        "sample_size_score": (
            report.sample_size_score
        ),
        "confidence_reliability_score": (
            report.confidence_reliability_score
        ),
        "stage_reliability_score": (
            report.stage_reliability_score
        ),
        "strongest_confidence_band": (
            report.strongest_confidence_band
        ),
        "weakest_confidence_band": (
            report.weakest_confidence_band
        ),
        "strongest_stage": (
            report.strongest_stage
        ),
        "weakest_stage": (
            report.weakest_stage
        ),
        "positive_reasons": list(
            report.positive_reasons
        ),
        "caution_reasons": list(
            report.caution_reasons
        ),
    }
