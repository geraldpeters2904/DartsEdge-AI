from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.services.strategy_service import evaluate_strategy, get_active_strategy, strategy_rules


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

    enforced = rules["enforcement_mode"] == "active" and rules["decision_rules_enabled"]
    if not enforced:
        effective_decision = official_decision
        effective_stake = round(max(0.0, float(official_stake)), 2)
    elif evaluation.qualifies:
        effective_decision = "Paper only" if rules["mode"] == "paper" else "Accept"
        effective_stake = evaluation.suggested_stake
    else:
        effective_decision = "Reject"
        effective_stake = 0.0

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
    }
