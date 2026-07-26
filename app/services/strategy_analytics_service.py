from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.strategy_decision import StrategyDecision
from app.services.decision_engine_service import DecisionEngineResult
from app.services.strategy_service import get_active_strategy, strategy_rules


@dataclass(frozen=True)
class StrategyMetric:
    strategy_name: str
    strategy_version: int
    decisions: int
    accepted: int
    rejected: int
    paper_only: int
    settled: int
    wins: int
    total_staked: float
    profit_loss: float
    roi_percent: Optional[float]
    win_rate_percent: Optional[float]
    acceptance_rate_percent: float
    average_ev_percent: float
    average_edge_percent: float
    maximum_drawdown: float


def record_decision(
    db: Session,
    *,
    result: DecisionEngineResult,
    strategy_uuid: str,
    bookmaker: str,
    model_probability: float,
    confidence_percent: float,
    decimal_odds: float,
    edge_percent: float,
    expected_value_percent: float,
    market: str,
    competition: str,
) -> StrategyDecision:
    row = StrategyDecision(
        strategy_uuid=strategy_uuid,
        strategy_name=result.strategy_name,
        strategy_version=result.strategy_version,
        enforcement_mode="active" if result.enforced else "shadow",
        trading_mode=result.mode,
        competition=(competition or "").strip(),
        market=(market or "match_winner").strip(),
        bookmaker=(bookmaker or "").strip(),
        model_probability=float(model_probability),
        confidence_percent=float(confidence_percent),
        decimal_odds=float(decimal_odds),
        edge_percent=float(edge_percent),
        expected_value_percent=float(expected_value_percent),
        official_decision=result.official_decision,
        official_stake=float(result.official_stake),
        strategy_decision=result.strategy_decision,
        strategy_stake=float(result.strategy_stake),
        effective_decision=result.effective_decision,
        effective_stake=float(result.effective_stake),
        blockers_json=json.dumps(list(result.blockers)),
        warnings_json=json.dumps(list(result.warnings)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def settle_decision(db: Session, decision_id: int, outcome: str) -> StrategyDecision:
    row = db.query(StrategyDecision).filter(StrategyDecision.id == decision_id).first()
    if row is None:
        raise ValueError("Strategy decision not found.")
    normalised = outcome.strip().lower()
    if normalised not in {"win", "loss", "void"}:
        raise ValueError("Outcome must be win, loss or void.")
    stake = float(row.effective_stake or 0.0)
    if normalised == "win":
        profit_loss = stake * (float(row.decimal_odds) - 1.0)
    elif normalised == "loss":
        profit_loss = -stake
    else:
        profit_loss = 0.0
    row.outcome = normalised
    row.profit_loss = round(profit_loss, 2)
    row.settled_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def _max_drawdown(rows: Iterable[StrategyDecision]) -> float:
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for row in sorted(rows, key=lambda item: item.created_at):
        equity += float(row.profit_loss or 0.0)
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return round(max_drawdown, 2)


def _metric(name: str, version: int, rows: list[StrategyDecision]) -> StrategyMetric:
    accepted_rows = [r for r in rows if r.effective_decision.lower() in {"accept", "consider"}]
    rejected = sum(r.effective_decision.lower() == "reject" for r in rows)
    paper_only = sum(r.effective_decision.lower() == "paper only" for r in rows)
    settled_rows = [r for r in rows if r.outcome in {"win", "loss", "void"}]
    wins = sum(r.outcome == "win" for r in settled_rows)
    staked_rows = [r for r in settled_rows if float(r.effective_stake or 0) > 0]
    total_staked = sum(float(r.effective_stake or 0) for r in staked_rows)
    pnl = sum(float(r.profit_loss or 0) for r in settled_rows)
    roi = (pnl / total_staked * 100) if total_staked > 0 else None
    win_denominator = sum(r.outcome in {"win", "loss"} for r in settled_rows)
    win_rate = (wins / win_denominator * 100) if win_denominator else None
    return StrategyMetric(
        strategy_name=name,
        strategy_version=version,
        decisions=len(rows),
        accepted=len(accepted_rows),
        rejected=rejected,
        paper_only=paper_only,
        settled=len(settled_rows),
        wins=wins,
        total_staked=round(total_staked, 2),
        profit_loss=round(pnl, 2),
        roi_percent=round(roi, 2) if roi is not None else None,
        win_rate_percent=round(win_rate, 2) if win_rate is not None else None,
        acceptance_rate_percent=round((len(accepted_rows) + paper_only) / len(rows) * 100, 2) if rows else 0.0,
        average_ev_percent=round(sum(r.expected_value_percent for r in rows) / len(rows), 2) if rows else 0.0,
        average_edge_percent=round(sum(r.edge_percent for r in rows) / len(rows), 2) if rows else 0.0,
        maximum_drawdown=_max_drawdown(settled_rows),
    )


def analytics(db: Session, days: Optional[int] = None) -> dict:
    query = db.query(StrategyDecision)
    if days:
        query = query.filter(StrategyDecision.created_at >= datetime.utcnow() - timedelta(days=days))
    rows = query.order_by(StrategyDecision.created_at.desc()).all()

    grouped = defaultdict(list)
    for row in rows:
        grouped[(row.strategy_name, row.strategy_version)].append(row)
    metrics = [_metric(name, version, items) for (name, version), items in grouped.items()]
    metrics.sort(key=lambda item: (item.roi_percent is not None, item.roi_percent or -9999, item.decisions), reverse=True)

    blockers = Counter()
    for row in rows:
        try:
            blockers.update(json.loads(row.blockers_json or "[]"))
        except (json.JSONDecodeError, TypeError):
            pass

    competitions = defaultdict(lambda: {"decisions": 0, "settled": 0, "profit_loss": 0.0})
    for row in rows:
        key = row.competition or "Unspecified"
        competitions[key]["decisions"] += 1
        if row.outcome:
            competitions[key]["settled"] += 1
            competitions[key]["profit_loss"] += float(row.profit_loss or 0)

    active = get_active_strategy(db)
    active_rules = strategy_rules(active)
    return {
        "active_strategy": {"name": active.name, "version": active.version, "uuid": active.strategy_uuid, "mode": active_rules["mode"]},
        "metrics": metrics,
        "recent": rows[:50],
        "total_decisions": len(rows),
        "settled_decisions": sum(bool(r.outcome) for r in rows),
        "rejection_reasons": blockers.most_common(10),
        "competitions": sorted(
            [{"name": name, "decisions": value["decisions"], "settled": value["settled"], "profit_loss": round(value["profit_loss"], 2)} for name, value in competitions.items()],
            key=lambda item: item["decisions"], reverse=True,
        ),
        "window_days": days,
        "insufficient_data": sum(bool(r.outcome) for r in rows) < 25,
    }
