from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class EvidenceBreakdown:
    model_quality: float
    trust_quality: float
    stability_quality: float
    history_quality: float
    value_quality: float


@dataclass(frozen=True)
class PredictionEvidence:
    evidence_score: int
    evidence_grade: str

    model_probability: float
    model_confidence: float
    trust_score: Optional[int]
    stability_score: Optional[int]

    historical_matches: int
    edge_percent: Optional[float]
    expected_value_percent: Optional[float]

    strongest_feature: Optional[str]
    most_sensitive_feature: Optional[str]

    breakdown: EvidenceBreakdown

    positive_reasons: tuple[str, ...]
    caution_reasons: tuple[str, ...]


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _optional_number(
    value: Any,
) -> Optional[float]:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    value: float,
    *,
    minimum: float,
    target: float,
) -> float:
    if target <= minimum:
        return 100.0

    proportion = (
        float(value)
        - float(minimum)
    ) / (
        float(target)
        - float(minimum)
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


def _grade(
    score: int,
) -> str:
    if score >= 90:
        return "Elite"

    if score >= 80:
        return "Strong"

    if score >= 70:
        return "Good"

    if score >= 60:
        return "Moderate"

    if score >= 45:
        return "Limited"

    return "Weak"


def _history_score(
    player_a_matches: int,
    player_b_matches: int,
) -> tuple[int, float]:
    minimum_history = min(
        max(
            int(player_a_matches),
            0,
        ),
        max(
            int(player_b_matches),
            0,
        ),
    )

    if minimum_history >= 100:
        return minimum_history, 100.0

    if minimum_history >= 50:
        return minimum_history, 90.0

    if minimum_history >= 25:
        return minimum_history, 75.0

    if minimum_history >= 15:
        return minimum_history, 60.0

    if minimum_history >= 10:
        return minimum_history, 45.0

    if minimum_history >= 5:
        return minimum_history, 25.0

    return minimum_history, 0.0


def _value_score(
    *,
    edge_percent: Optional[float],
    expected_value_percent: Optional[float],
) -> float:
    if (
        edge_percent is None
        or expected_value_percent is None
    ):
        return 40.0

    edge = _scale(
        edge_percent,
        minimum=0.0,
        target=15.0,
    )

    expected_value = _scale(
        expected_value_percent,
        minimum=0.0,
        target=20.0,
    )

    return round(
        edge * 0.45
        + expected_value * 0.55,
        2,
    )


def _strongest_feature(
    opportunity: dict,
) -> Optional[str]:
    contributions = (
        opportunity.get(
            "contributions"
        )
        or []
    )

    if not contributions:
        return None

    strongest = max(
        contributions,
        key=lambda item: abs(
            _number(
                item.get(
                    "weighted_score"
                )
            )
        ),
    )

    return (
        strongest.get("label")
        or str(
            strongest.get("feature")
            or ""
        )
        .replace("_", " ")
        .title()
        or None
    )


def build_prediction_evidence(
    *,
    opportunity: dict,
    trust_report=None,
    stability_report=None,
    assessment=None,
) -> PredictionEvidence:
    probability = _number(
        opportunity.get(
            "probability"
        )
    )

    model_confidence = _number(
        opportunity.get(
            "model_confidence"
        )
    )

    player_a_history = int(
        _number(
            opportunity.get(
                "player_a_history_matches"
            )
        )
    )

    player_b_history = int(
        _number(
            opportunity.get(
                "player_b_history_matches"
            )
        )
    )

    historical_matches, history_quality = (
        _history_score(
            player_a_history,
            player_b_history,
        )
    )

    trust_score = (
        int(
            trust_report.trust_score
        )
        if trust_report is not None
        else None
    )

    stability_score = (
        int(
            stability_report
            .stability_score
        )
        if stability_report is not None
        else None
    )

    edge_percent = (
        _optional_number(
            assessment.edge_percent
        )
        if assessment is not None
        else _optional_number(
            opportunity.get(
                "edge_percent"
            )
        )
    )

    expected_value_percent = (
        _optional_number(
            assessment
            .expected_value_percent
        )
        if assessment is not None
        else _optional_number(
            opportunity.get(
                "expected_value_percent"
            )
        )
    )

    model_quality = round(
        _scale(
            probability,
            minimum=50.0,
            target=75.0,
        )
        * 0.55
        + _scale(
            model_confidence,
            minimum=40.0,
            target=85.0,
        )
        * 0.45,
        2,
    )

    trust_quality = (
        float(trust_score)
        if trust_score is not None
        else 50.0
    )

    stability_quality = (
        float(stability_score)
        if stability_score is not None
        else 50.0
    )

    value_quality = _value_score(
        edge_percent=edge_percent,
        expected_value_percent=(
            expected_value_percent
        ),
    )

    breakdown = EvidenceBreakdown(
        model_quality=model_quality,
        trust_quality=(
            trust_quality
        ),
        stability_quality=(
            stability_quality
        ),
        history_quality=(
            history_quality
        ),
        value_quality=value_quality,
    )

    weighted_score = (
        model_quality * 0.25
        + trust_quality * 0.25
        + stability_quality * 0.20
        + history_quality * 0.15
        + value_quality * 0.15
    )

    evidence_score = int(
        round(
            _clamp(
                weighted_score
            )
        )
    )

    positive: list[str] = []
    cautions: list[str] = []

    if probability >= 60.0:
        positive.append(
            "The model shows meaningful separation between the players."
        )
    elif probability < 55.0:
        cautions.append(
            "The model sees only a small difference between the players."
        )

    if model_confidence >= 75.0:
        positive.append(
            "Model confidence is high."
        )
    elif model_confidence < 60.0:
        cautions.append(
            "Model confidence is below the preferred level."
        )

    if trust_score is None:
        cautions.append(
            "Model trust is not currently available."
        )
    elif trust_score >= 70:
        positive.append(
            "Historical model trust is strong."
        )
    elif trust_score < 55:
        cautions.append(
            "Historical model trust is limited."
        )

    if stability_score is None:
        cautions.append(
            "Prediction stability has not been calculated."
        )
    elif stability_score >= 80:
        positive.append(
            "The prediction is robust to small rating changes."
        )
    elif stability_score < 65:
        cautions.append(
            "The prediction is sensitive to small rating changes."
        )

    if historical_matches >= 25:
        positive.append(
            "Both players have useful historical coverage."
        )
    elif historical_matches < 10:
        cautions.append(
            "At least one player has limited historical coverage."
        )

    if (
        edge_percent is not None
        and expected_value_percent
        is not None
    ):
        if (
            edge_percent >= 5.0
            and expected_value_percent
            > 0.0
        ):
            positive.append(
                "The available price offers positive model value."
            )
        elif expected_value_percent <= 0.0:
            cautions.append(
                "The current market price does not offer positive value."
            )
    else:
        cautions.append(
            "Market odds are required to confirm value."
        )

    strongest_feature = (
        _strongest_feature(
            opportunity
        )
    )

    most_sensitive_feature = (
        str(
            stability_report
            .most_sensitive_feature
        )
        .replace("_", " ")
        .title()
        if (
            stability_report is not None
            and stability_report
            .most_sensitive_feature
        )
        else None
    )

    return PredictionEvidence(
        evidence_score=(
            evidence_score
        ),
        evidence_grade=_grade(
            evidence_score
        ),
        model_probability=round(
            probability,
            2,
        ),
        model_confidence=round(
            model_confidence,
            2,
        ),
        trust_score=trust_score,
        stability_score=(
            stability_score
        ),
        historical_matches=(
            historical_matches
        ),
        edge_percent=(
            round(
                edge_percent,
                2,
            )
            if edge_percent is not None
            else None
        ),
        expected_value_percent=(
            round(
                expected_value_percent,
                2,
            )
            if expected_value_percent
            is not None
            else None
        ),
        strongest_feature=(
            strongest_feature
        ),
        most_sensitive_feature=(
            most_sensitive_feature
        ),
        breakdown=breakdown,
        positive_reasons=tuple(
            positive
        ),
        caution_reasons=tuple(
            cautions
        ),
    )


def evidence_summary(
    evidence: PredictionEvidence,
) -> dict:
    return {
        "evidence_score": (
            evidence.evidence_score
        ),
        "evidence_grade": (
            evidence.evidence_grade
        ),
        "model_probability": (
            evidence.model_probability
        ),
        "model_confidence": (
            evidence.model_confidence
        ),
        "trust_score": (
            evidence.trust_score
        ),
        "stability_score": (
            evidence.stability_score
        ),
        "historical_matches": (
            evidence.historical_matches
        ),
        "edge_percent": (
            evidence.edge_percent
        ),
        "expected_value_percent": (
            evidence
            .expected_value_percent
        ),
        "strongest_feature": (
            evidence.strongest_feature
        ),
        "most_sensitive_feature": (
            evidence
            .most_sensitive_feature
        ),
        "breakdown": {
            "model_quality": (
                evidence.breakdown
                .model_quality
            ),
            "trust_quality": (
                evidence.breakdown
                .trust_quality
            ),
            "stability_quality": (
                evidence.breakdown
                .stability_quality
            ),
            "history_quality": (
                evidence.breakdown
                .history_quality
            ),
            "value_quality": (
                evidence.breakdown
                .value_quality
            ),
        },
        "positive_reasons": list(
            evidence.positive_reasons
        ),
        "caution_reasons": list(
            evidence.caution_reasons
        ),
    }
