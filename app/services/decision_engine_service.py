from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.services.strategy_service import (
    evaluate_strategy,
    get_active_strategy,
    strategy_rules,
)


@dataclass(frozen=True)
class DecisionEngineResult:
    official_decision: str
    official_stake: float
    strategy_decision: str
    strategy_stake: float
    effective_decision: str
    effective_stake: float
    qualifies: bool
    enforced: bool
    strategy_name: str
    strategy_version: int
    mode: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    decision_score: int
    decision_grade: str
    positive_reasons: tuple[str, ...]
    negative_reasons: tuple[str, ...]


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(float(value), minimum), maximum)


def _scaled_score(
    value: float,
    *,
    minimum: float,
    target: float,
    maximum_points: float,
) -> float:
    if target <= minimum:
        return float(maximum_points)
    proportion = (float(value) - minimum) / (target - minimum)
    return _clamp(proportion, 0.0, 1.0) * float(maximum_points)


def _decision_grade(score: int) -> str:
    if score >= 90:
        return "Elite"
    if score >= 80:
        return "Strong"
    if score >= 70:
        return "Moderate"
    if score >= 60:
        return "Watch"
    return "Pass"


def _score_decision(
    *,
    model_probability: float,
    confidence_percent: float,
    expected_value_percent: float,
    edge_percent: float,
    decimal_odds: float,
    official_stake: float,
    bankroll: float,
    sample_size: int,
    portfolio_exposure_percent: Optional[float],
    maximum_portfolio_exposure_percent: float,
    maximum_decimal_odds: float,
    qualifies: bool,
    blockers: tuple[str, ...],
    warnings: tuple[str, ...],
) -> tuple[int, str, tuple[str, ...], tuple[str, ...]]:
    positive: list[str] = []
    negative: list[str] = []
    score = 0.0

    score += _scaled_score(
        model_probability,
        minimum=50.0,
        target=75.0,
        maximum_points=20.0,
    )
    if model_probability >= 65.0:
        positive.append("Model probability is strong.")
    elif model_probability < 55.0:
        negative.append("Model probability is relatively weak.")

    score += _scaled_score(
        confidence_percent,
        minimum=40.0,
        target=85.0,
        maximum_points=15.0,
    )
    if confidence_percent >= 75.0:
        positive.append("Model confidence is high.")
    elif confidence_percent < 60.0:
        negative.append("Model confidence is below the preferred level.")

    score += _scaled_score(
        expected_value_percent,
        minimum=0.0,
        target=20.0,
        maximum_points=25.0,
    )
    if expected_value_percent >= 10.0:
        positive.append("Expected value is strong.")
    elif expected_value_percent <= 0.0:
        negative.append("Expected value is not positive.")

    score += _scaled_score(
        edge_percent,
        minimum=0.0,
        target=15.0,
        maximum_points=20.0,
    )
    if edge_percent >= 8.0:
        positive.append("The model has a meaningful market edge.")
    elif edge_percent < 5.0:
        negative.append("The model edge is below the preferred level.")

    bankroll_value = max(float(bankroll), 0.0)
    stake_value = max(float(official_stake), 0.0)
    stake_percent = (
        stake_value / bankroll_value * 100.0
        if bankroll_value > 0
        else 0.0
    )
    if 0.0 < stake_percent <= 3.0:
        score += 8.0
        positive.append("The proposed stake is within a controlled bankroll range.")
    elif stake_percent > 3.0:
        score += 3.0
        negative.append("The proposed stake is relatively large for the bankroll.")
    else:
        negative.append("No positive stake is currently recommended.")

    if sample_size >= 50:
        score += 5.0
        positive.append("The decision is supported by a strong sample size.")
    elif sample_size >= 20:
        score += 3.0
    elif sample_size > 0:
        score += 1.0
        negative.append("The supporting sample size is limited.")
    else:
        negative.append("No supporting sample size was supplied.")

    if portfolio_exposure_percent is None:
        score += 2.0
        negative.append("Portfolio exposure is unavailable.")
    else:
        exposure = max(float(portfolio_exposure_percent), 0.0)
        if exposure <= maximum_portfolio_exposure_percent * 0.50:
            score += 5.0
            positive.append("Portfolio exposure has comfortable capacity.")
        elif exposure <= maximum_portfolio_exposure_percent:
            score += 3.0
        else:
            negative.append("Portfolio exposure exceeds the strategy limit.")

    if float(decimal_odds) <= float(maximum_decimal_odds):
        score += 2.0
    else:
        negative.append("The available price exceeds the strategy limit.")

    negative.extend(
        str(message)
        for message in blockers
        if str(message) not in negative
    )
    for warning in warnings:
        text = str(warning)
        if text not in negative:
            negative.append(text)

    if not qualifies:
        score = min(score, 59.0)

    final_score = int(round(_clamp(score, 0.0, 100.0)))
    return (
        final_score,
        _decision_grade(final_score),
        tuple(positive),
        tuple(negative),
    )


def decide(
    db,
    *,
    official_decision: str,
    official_stake: float,
    model_probability: float,
    confidence_percent: float,
    expected_value_percent: float,
    edge_percent: float,
    decimal_odds: float,
    bankroll: float,
    market: str = "match_winner",
    competition: str = "",
    sample_size: int = 0,
    portfolio_exposure_percent: Optional[float] = None,
) -> DecisionEngineResult:
    strategy = get_active_strategy(db)
    rules = strategy_rules(strategy)
    evaluation = evaluate_strategy(
        strategy,
        model_probability=model_probability,
        confidence_percent=confidence_percent,
        expected_value_percent=expected_value_percent,
        edge_percent=edge_percent,
        decimal_odds=decimal_odds,
        bankroll=bankroll,
        raw_kelly_stake=official_stake,
        market=market,
        competition=competition,
        sample_size=sample_size,
        portfolio_exposure_percent=portfolio_exposure_percent,
    )

    enforced = (
        rules["enforcement_mode"] == "active"
        and rules["decision_rules_enabled"]
    )
    if not enforced:
        effective_decision = official_decision
        effective_stake = round(max(0.0, float(official_stake)), 2)
    elif evaluation.qualifies:
        effective_decision = (
            "Paper only" if rules["mode"] == "paper" else "Accept"
        )
        effective_stake = evaluation.suggested_stake
    else:
        effective_decision = "Reject"
        effective_stake = 0.0

    score, grade, positive, negative = _score_decision(
        model_probability=model_probability,
        confidence_percent=confidence_percent,
        expected_value_percent=expected_value_percent,
        edge_percent=edge_percent,
        decimal_odds=decimal_odds,
        official_stake=official_stake,
        bankroll=bankroll,
        sample_size=sample_size,
        portfolio_exposure_percent=portfolio_exposure_percent,
        maximum_portfolio_exposure_percent=rules[
            "maximum_portfolio_exposure_percent"
        ],
        maximum_decimal_odds=rules["maximum_decimal_odds"],
        qualifies=evaluation.qualifies,
        blockers=evaluation.blockers,
        warnings=evaluation.warnings,
    )

    return DecisionEngineResult(
        official_decision=official_decision,
        official_stake=round(max(0.0, float(official_stake)), 2),
        strategy_decision="Accept" if evaluation.qualifies else "Reject",
        strategy_stake=evaluation.suggested_stake,
        effective_decision=effective_decision,
        effective_stake=effective_stake,
        qualifies=evaluation.qualifies,
        enforced=enforced,
        strategy_name=strategy.name,
        strategy_version=strategy.version,
        mode=rules["mode"],
        blockers=evaluation.blockers,
        warnings=evaluation.warnings,
        decision_score=score,
        decision_grade=grade,
        positive_reasons=positive,
        negative_reasons=negative,
    )


def summary(result: DecisionEngineResult) -> Dict[str, Any]:
    return {
        "official_decision": result.official_decision,
        "official_stake": result.official_stake,
        "strategy_decision": result.strategy_decision,
        "strategy_stake": result.strategy_stake,
        "effective_decision": result.effective_decision,
        "effective_stake": result.effective_stake,
        "qualifies": result.qualifies,
        "enforced": result.enforced,
        "strategy_name": result.strategy_name,
        "strategy_version": result.strategy_version,
        "mode": result.mode,
        "blockers": list(result.blockers),
        "warnings": list(result.warnings),
        "decision_score": result.decision_score,
        "decision_grade": result.decision_grade,
        "positive_reasons": list(result.positive_reasons),
        "negative_reasons": list(result.negative_reasons),
    }
