from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class DecisionIntelligenceBreakdown:
    value: float
    model: float
    trust: float
    market: float
    portfolio: float


@dataclass(frozen=True)
class DecisionIntelligenceReport:
    score: int
    grade: str
    recommendation: str
    stars: int
    model_probability: float
    model_confidence: float
    evidence_score: Optional[float]
    trust_score: Optional[float]
    expected_value_percent: float
    edge_percent: float
    market_direction: Optional[str]
    market_volatility: Optional[str]
    clv_percent: Optional[float]
    consensus_score: Optional[float]
    steam_direction: Optional[str]
    steam_strength: Optional[str]
    coordinated_move: bool
    portfolio_exposure_percent: Optional[float]
    suggested_stake: float
    breakdown: DecisionIntelligenceBreakdown
    positive_reasons: tuple[str, ...]
    caution_reasons: tuple[str, ...]


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _optional_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return min(max(float(value), minimum), maximum)


def _scaled(value: float, *, minimum: float, target: float) -> float:
    if target <= minimum:
        return 100.0
    proportion = (float(value) - float(minimum)) / (float(target) - float(minimum))
    return round(_clamp(proportion, 0.0, 1.0) * 100.0, 2)


def _grade(score: int) -> tuple[str, str, int]:
    if score >= 90:
        return ("Premium", "BET", 5)
    if score >= 80:
        return ("Excellent", "BET", 4)
    if score >= 70:
        return ("Strong", "SMALL BET", 3)
    if score >= 55:
        return ("Watch", "WATCH", 2)
    return ("Pass", "NO BET", 1)


def _market_score(
    *,
    direction: Optional[str],
    volatility: Optional[str],
    clv_percent: Optional[float],
    consensus_score: Optional[float],
    steam_direction: Optional[str],
    steam_strength: Optional[str],
    coordinated_move: bool,
) -> tuple[float, list[str], list[str]]:
    score = 50.0
    positive: list[str] = []
    cautions: list[str] = []

    normalised_direction = (direction or "").strip().lower()
    if normalised_direction == "shortening":
        score += 10.0
        positive.append("The market is shortening on the selection.")
    elif normalised_direction == "drifting":
        score -= 8.0
        cautions.append("The market is drifting against the selection.")

    normalised_volatility = (volatility or "").strip().lower()
    if normalised_volatility == "low":
        score += 8.0
        positive.append("Market volatility is low.")
    elif normalised_volatility == "medium":
        score += 2.0
    elif normalised_volatility == "high":
        score -= 7.0
        cautions.append("Market volatility is high.")
    elif normalised_volatility == "extreme":
        score -= 12.0
        cautions.append("Market volatility is extreme.")

    if clv_percent is not None:
        if clv_percent >= 2.0:
            score += 16.0
            positive.append("The available position shows strong positive CLV.")
        elif clv_percent > 0.0:
            score += 8.0
            positive.append("The available position shows positive CLV.")
        elif clv_percent < -2.0:
            score -= 16.0
            cautions.append("The available position shows materially negative CLV.")
        elif clv_percent < 0.0:
            score -= 8.0
            cautions.append("The available position shows negative CLV.")

    if consensus_score is not None:
        if consensus_score >= 85.0:
            score += 10.0
            positive.append("Bookmaker consensus is very strong.")
        elif consensus_score >= 70.0:
            score += 5.0
            positive.append("Bookmaker consensus is strong.")
        elif consensus_score < 45.0:
            score -= 10.0
            cautions.append("Bookmaker prices show weak consensus.")

    steam = (steam_direction or "").strip().lower()
    strength = (steam_strength or "").strip().lower()

    strength_bonus = {
        "light": 4.0,
        "medium": 8.0,
        "strong": 12.0,
    }.get(strength, 0.0)

    if coordinated_move and steam == "shortening":
        score += strength_bonus
        positive.append(
            f"Coordinated {strength or 'market'} shortening supports the selection."
        )
    elif coordinated_move and steam == "drifting":
        score -= strength_bonus
        cautions.append(
            f"Coordinated {strength or 'market'} drift moves against the selection."
        )

    return round(_clamp(score), 2), positive, cautions


def build_decision_intelligence(
    *,
    model_probability: float,
    model_confidence: float,
    expected_value_percent: float,
    edge_percent: float,
    suggested_stake: float,
    bankroll: float,
    evidence_score: Optional[float] = None,
    trust_score: Optional[float] = None,
    portfolio_exposure_percent: Optional[float] = None,
    maximum_portfolio_exposure_percent: float = 10.0,
    market_direction: Optional[str] = None,
    market_volatility: Optional[str] = None,
    clv_percent: Optional[float] = None,
    consensus_score: Optional[float] = None,
    steam_direction: Optional[str] = None,
    steam_strength: Optional[str] = None,
    coordinated_move: bool = False,
    strategy_qualifies: bool = True,
    strategy_blockers: tuple[str, ...] = (),
) -> DecisionIntelligenceReport:
    probability = _number(model_probability)
    confidence = _number(model_confidence)
    ev = _number(expected_value_percent)
    edge = _number(edge_percent)
    stake = max(_number(suggested_stake), 0.0)
    bankroll_value = max(_number(bankroll), 0.0)
    evidence = _optional_number(evidence_score)
    trust = _optional_number(trust_score)
    exposure = _optional_number(portfolio_exposure_percent)
    consensus = _optional_number(consensus_score)

    positive: list[str] = []
    cautions: list[str] = []

    value_quality = round(
        _scaled(ev, minimum=0.0, target=20.0) * 0.60
        + _scaled(edge, minimum=0.0, target=15.0) * 0.40,
        2,
    )

    if ev >= 8.0:
        positive.append("Expected value is strong.")
    elif ev <= 0.0:
        cautions.append("Expected value is not positive.")

    if edge >= 5.0:
        positive.append("The model has a meaningful edge over the available price.")
    elif edge < 2.0:
        cautions.append("The model edge is small.")

    model_probability_quality = _scaled(
        probability,
        minimum=50.0,
        target=75.0,
    )

    confidence_quality = _scaled(
        confidence,
        minimum=40.0,
        target=85.0,
    )

    evidence_quality = _clamp(evidence) if evidence is not None else 50.0

    model_quality = round(
        model_probability_quality * 0.35
        + confidence_quality * 0.30
        + evidence_quality * 0.35,
        2,
    )

    if probability >= 60.0:
        positive.append("The model shows useful separation between the players.")
    elif probability < 55.0:
        cautions.append("The model sees only a small difference between the players.")

    if evidence is not None:
        if evidence >= 75.0:
            positive.append("Prediction evidence is strong.")
        elif evidence < 55.0:
            cautions.append("Prediction evidence is limited.")

    trust_quality = _clamp(trust) if trust is not None else 50.0

    if trust is not None:
        if trust >= 70.0:
            positive.append("Historical model trust is strong.")
        elif trust < 55.0:
            cautions.append("Historical model trust is limited.")
    else:
        cautions.append("Model Trust is not available.")

    market_quality, market_positive, market_cautions = _market_score(
        direction=market_direction,
        volatility=market_volatility,
        clv_percent=clv_percent,
        consensus_score=consensus,
        steam_direction=steam_direction,
        steam_strength=steam_strength,
        coordinated_move=coordinated_move,
    )

    positive.extend(market_positive)
    cautions.extend(market_cautions)

    max_exposure = max(float(maximum_portfolio_exposure_percent), 0.1)

    if exposure is None:
        portfolio_quality = 50.0
        cautions.append("Portfolio exposure is unavailable.")
    elif exposure <= max_exposure * 0.50:
        portfolio_quality = 100.0
        positive.append("Portfolio exposure has comfortable capacity.")
    elif exposure <= max_exposure:
        portfolio_quality = 70.0
    else:
        portfolio_quality = 10.0
        cautions.append("Portfolio exposure exceeds the preferred limit.")

    if bankroll_value > 0.0:
        stake_percent = stake / bankroll_value * 100.0

        if 0.0 < stake_percent <= 3.0:
            positive.append("The suggested stake is within a controlled bankroll range.")
        elif stake_percent > 3.0:
            portfolio_quality = min(portfolio_quality, 55.0)
            cautions.append("The suggested stake is relatively large for the bankroll.")
    elif stake > 0.0:
        cautions.append("A positive stake is suggested but bankroll is unavailable.")

    breakdown = DecisionIntelligenceBreakdown(
        value=value_quality,
        model=model_quality,
        trust=trust_quality,
        market=market_quality,
        portfolio=portfolio_quality,
    )

    weighted_score = (
        value_quality * 0.30
        + model_quality * 0.25
        + trust_quality * 0.15
        + market_quality * 0.20
        + portfolio_quality * 0.10
    )

    if not strategy_qualifies:
        weighted_score = min(weighted_score, 59.0)
        for blocker in strategy_blockers:
            text = str(blocker)
            if text not in cautions:
                cautions.append(text)

    score = int(round(_clamp(weighted_score)))
    grade, recommendation, stars = _grade(score)

    return DecisionIntelligenceReport(
        score=score,
        grade=grade,
        recommendation=recommendation,
        stars=stars,
        model_probability=round(probability, 2),
        model_confidence=round(confidence, 2),
        evidence_score=round(evidence, 2) if evidence is not None else None,
        trust_score=round(trust, 2) if trust is not None else None,
        expected_value_percent=round(ev, 2),
        edge_percent=round(edge, 2),
        market_direction=market_direction,
        market_volatility=market_volatility,
        clv_percent=round(clv_percent, 2) if clv_percent is not None else None,
        consensus_score=round(consensus, 2) if consensus is not None else None,
        steam_direction=steam_direction,
        steam_strength=steam_strength,
        coordinated_move=bool(coordinated_move),
        portfolio_exposure_percent=(
            round(exposure, 2)
            if exposure is not None
            else None
        ),
        suggested_stake=round(stake, 2),
        breakdown=breakdown,
        positive_reasons=tuple(positive),
        caution_reasons=tuple(cautions),
    )


def decision_intelligence_summary(report: DecisionIntelligenceReport) -> dict:
    return {
        "score": report.score,
        "grade": report.grade,
        "recommendation": report.recommendation,
        "stars": report.stars,
        "model_probability": report.model_probability,
        "model_confidence": report.model_confidence,
        "evidence_score": report.evidence_score,
        "trust_score": report.trust_score,
        "expected_value_percent": report.expected_value_percent,
        "edge_percent": report.edge_percent,
        "market_direction": report.market_direction,
        "market_volatility": report.market_volatility,
        "clv_percent": report.clv_percent,
        "consensus_score": report.consensus_score,
        "steam_direction": report.steam_direction,
        "steam_strength": report.steam_strength,
        "coordinated_move": report.coordinated_move,
        "portfolio_exposure_percent": report.portfolio_exposure_percent,
        "suggested_stake": report.suggested_stake,
        "breakdown": {
            "value": report.breakdown.value,
            "model": report.breakdown.model,
            "trust": report.breakdown.trust,
            "market": report.breakdown.market,
            "portfolio": report.breakdown.portfolio,
        },
        "positive_reasons": list(report.positive_reasons),
        "caution_reasons": list(report.caution_reasons),
    }
