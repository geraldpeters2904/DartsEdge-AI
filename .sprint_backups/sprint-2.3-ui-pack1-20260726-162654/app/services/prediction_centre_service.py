from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from app.models.match import Match
from app.services.ai_coach_service import build_ai_coach_data
from app.services.daily_briefing_service import _value_opportunities
from app.services.opportunity_ranking_service import build_ranked_opportunities
from app.services.portfolio_health_service import build_portfolio_health
from app.services.strategy_service import get_active_strategy, strategy_summary


def _normalise(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _fixture_key(player_a: str, player_b: str) -> frozenset[str]:
    return frozenset((_normalise(player_a), _normalise(player_b)))


def build_prediction_centre(db, *, limit: int = 30) -> Dict[str, Any]:
    """Build the read-only operational workspace for today's fixtures.

    Pack 1 aggregates existing services only. It does not write predictions,
    odds, decisions or audit records.
    """
    today = date.today()
    fixtures = (
        db.query(Match)
        .filter(Match.date == today, Match.status == "scheduled")
        .order_by(Match.id.asc())
        .limit(max(1, min(limit, 100)))
        .all()
    )

    ranked = build_ranked_opportunities(db, limit=max(limit, 100))
    ranked_by_match = {item.get("match_id"): item for item in ranked if item.get("match_id")}
    ranked_by_players = {
        _fixture_key(item.get("player_a", ""), item.get("player_b", "")): item
        for item in ranked
    }

    values = _value_opportunities(db, limit=100)
    value_by_match = {item.get("match_id"): item for item in values if item.get("match_id")}
    value_by_players = {
        _fixture_key(item.get("player_a", ""), item.get("player_b", "")): item
        for item in values
    }

    cards: List[Dict[str, Any]] = []
    for fixture in fixtures:
        key = _fixture_key(fixture.player_a, fixture.player_b)
        opportunity = ranked_by_match.get(fixture.id) or ranked_by_players.get(key)
        value = value_by_match.get(fixture.id) or value_by_players.get(key)
        assessment = value.get("assessment") if value else None
        price = value.get("price") if value else None

        if assessment and assessment.has_value:
            tone = "good"
            status = "Positive EV"
        elif opportunity:
            tone = "warning"
            status = "Odds required" if not price else "No value"
        else:
            tone = "neutral"
            status = "Analysis unavailable"

        cards.append({
            "fixture": fixture,
            "opportunity": opportunity,
            "value": value,
            "assessment": assessment,
            "price": price,
            "status": status,
            "tone": tone,
        })

    portfolio = build_portfolio_health(db)
    coach = build_ai_coach_data(db)
    active_strategy = strategy_summary(get_active_strategy(db))
    confirmed = [card for card in cards if card["assessment"] and card["assessment"].has_value]

    return {
        "centre_date": today,
        "cards": cards,
        "fixture_count": len(cards),
        "confirmed_value_count": len(confirmed),
        "top_card": confirmed[0] if confirmed else (cards[0] if cards else None),
        "portfolio": portfolio,
        "coach": coach,
        "active_strategy": active_strategy,
        "decision_engine_active": (
            active_strategy["decision_rules_enabled"]
            and active_strategy["enforcement_mode"] == "active"
        ),
    }
