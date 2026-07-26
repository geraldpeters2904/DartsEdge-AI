from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from app.services.best_bets_service import build_best_bets


CONFIDENCE_WEIGHTS = {
    "Elite": 100.0,
    "Very Strong": 94.0,
    "High": 90.0,
    "Strong": 84.0,
    "Good": 76.0,
    "Moderate": 64.0,
    "Low": 45.0,
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalised_probability(value: Any) -> float:
    probability = _number(value)
    if 0.0 <= probability <= 1.0:
        probability *= 100.0
    return max(0.0, min(probability, 100.0))


def _urgency_score(fixture_date: Any, today: date) -> float:
    if not fixture_date:
        return 35.0

    if hasattr(fixture_date, "date") and not isinstance(fixture_date, date):
        fixture_date = fixture_date.date()

    days_away = (fixture_date - today).days

    if days_away < 0:
        return 0.0
    if days_away == 0:
        return 100.0
    if days_away == 1:
        return 85.0
    if days_away <= 3:
        return 70.0
    if days_away <= 7:
        return 55.0
    return 35.0


def _value_metrics(
    probability: float,
    fair_odds: float,
    market_odds: Optional[float],
) -> Dict[str, Any]:
    if not market_odds or market_odds <= 1.0 or probability <= 0:
        return {
            "market_odds": None,
            "edge_percent": None,
            "value_score": 0.0,
            "is_value_confirmed": False,
            "status": "Odds required",
            "status_tone": "neutral",
        }

    implied_probability = 100.0 / market_odds
    edge_percent = probability - implied_probability
    expected_value_percent = ((probability / 100.0) * market_odds - 1.0) * 100.0
    value_score = max(0.0, min(expected_value_percent * 4.0, 100.0))
    is_value_confirmed = edge_percent >= 2.0 and expected_value_percent > 0.0

    return {
        "market_odds": round(market_odds, 2),
        "edge_percent": round(edge_percent, 2),
        "expected_value_percent": round(expected_value_percent, 2),
        "value_score": round(value_score, 1),
        "is_value_confirmed": is_value_confirmed,
        "status": "Value confirmed" if is_value_confirmed else "No value at current odds",
        "status_tone": "good" if is_value_confirmed else "risk",
    }


def rank_opportunity(
    opportunity: Dict[str, Any],
    *,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    today = today or date.today()
    probability = _normalised_probability(opportunity.get("probability"))
    stars = max(1, min(int(_number(opportunity.get("stars"), 1)), 5))
    confidence = str(opportunity.get("confidence") or "Low")
    confidence_score = CONFIDENCE_WEIGHTS.get(confidence, stars * 18.0)
    urgency_score = _urgency_score(opportunity.get("date"), today)

    fair_odds = _number(opportunity.get("fair_odds"))
    if fair_odds <= 0 and probability > 0:
        fair_odds = 100.0 / probability

    market_odds_raw = opportunity.get("market_odds")
    market_odds = _number(market_odds_raw) if market_odds_raw not in (None, "") else None
    value = _value_metrics(probability, fair_odds, market_odds)

    model_score = (
        probability * 0.55
        + confidence_score * 0.20
        + (stars / 5.0 * 100.0) * 0.15
        + urgency_score * 0.10
    )

    priority_score = model_score
    if value["market_odds"] is not None:
        priority_score = model_score * 0.75 + value["value_score"] * 0.25

    if value["is_value_confirmed"]:
        action = "Consider"
    elif value["market_odds"] is None:
        action = "Check odds"
    else:
        action = "Pass"

    return {
        **opportunity,
        "probability": round(probability, 1),
        "stars": stars,
        "confidence": confidence,
        "fair_odds": round(fair_odds, 2) if fair_odds else None,
        "model_score": round(model_score, 1),
        "priority_score": round(priority_score, 1),
        "urgency_score": round(urgency_score, 1),
        "action": action,
        **value,
    }


def rank_opportunities(
    opportunities: Iterable[Dict[str, Any]],
    *,
    today: Optional[date] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    ranked = [rank_opportunity(item, today=today) for item in opportunities]
    ranked.sort(
        key=lambda item: (
            item["is_value_confirmed"],
            item["priority_score"],
            item["probability"],
        ),
        reverse=True,
    )

    if limit is not None:
        ranked = ranked[:limit]

    for position, item in enumerate(ranked, start=1):
        item["rank"] = position

    return ranked


def build_ranked_opportunities(db, limit: int = 20) -> List[Dict[str, Any]]:
    candidates = build_best_bets(db, limit=max(limit, 50))
    return rank_opportunities(candidates, limit=limit)
