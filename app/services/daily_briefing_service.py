from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from app.models.match import Match
from app.services.ai_coach_service import build_ai_coach_data
from app.services.data_provider_service import DataProviderService
from app.services.expected_value_service import assess_value, best_prices, recent_snapshots
from app.services.model_performance_lab_service import build_model_performance_lab
from app.services.odds_provider_service import OddsProviderService
from app.services.opportunity_ranking_service import build_ranked_opportunities
from app.services.portfolio_health_service import build_portfolio_health
from app.services.settings_service import get_settings
from app.services.strategy_service import get_active_strategy, strategy_summary


def _normalise(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _match_price(opportunity: Dict[str, Any], prices) -> Any | None:
    selection = _normalise(opportunity.get("selection"))
    player_a = _normalise(opportunity.get("player_a"))
    player_b = _normalise(opportunity.get("player_b"))
    fixture_date = opportunity.get("date")
    for row in prices:
        same_players = {
            _normalise(row.player_a), _normalise(row.player_b)
        } == {player_a, player_b}
        if (not fixture_date or row.fixture_date == fixture_date) and same_players and _normalise(row.selection) == selection:
            return row
    return None


def _value_opportunities(db, limit: int = 10) -> List[Dict[str, Any]]:
    settings = get_settings(db)
    prices = best_prices(recent_snapshots(db, limit=500))
    ranked = build_ranked_opportunities(db, limit=100)
    results: List[Dict[str, Any]] = []
    for item in ranked:
        price = _match_price(item, prices)
        if not price:
            continue
        try:
            assessment = assess_value(
                model_probability=float(item["probability"]),
                decimal_odds=float(price.decimal_odds),
                bookmaker=price.bookmaker,
                bankroll=settings.bankroll,
                kelly_fraction=settings.kelly_fraction,
                max_daily_risk_percent=settings.max_daily_risk,
                minimum_edge_percent=settings.minimum_edge,
            )
        except ValueError:
            continue
        results.append({**item, "price": price, "assessment": assessment})
    results.sort(key=lambda row: row["assessment"].expected_value_percent, reverse=True)
    return results[:limit]


def build_daily_briefing(db) -> Dict[str, Any]:
    today = date.today()
    fixtures = (
        db.query(Match)
        .filter(Match.date == today, Match.status == "scheduled")
        .order_by(Match.id.asc())
        .all()
    )
    portfolio = build_portfolio_health(db)
    coach = build_ai_coach_data(db)
    performance = build_model_performance_lab(db)
    values = _value_opportunities(db)
    positive = [row for row in values if row["assessment"].is_value]
    top = positive[0] if positive else None
    data_diag = DataProviderService(db).diagnostics()
    odds_diag = OddsProviderService().diagnostics()
    active_strategy = strategy_summary(get_active_strategy(db))

    system_healthy = data_diag["healthy"] >= 1 and odds_diag["healthy"] >= 1
    if portfolio["risk_level"] == "risk":
        briefing_tone = "risk"
        headline = "Risk limit exceeded — pause new positions"
    elif top:
        briefing_tone = "good"
        headline = f"Top value signal: {top['selection']}"
    elif fixtures:
        briefing_tone = "warning"
        headline = "Fixtures are ready; confirmed value is still required"
    else:
        briefing_tone = "neutral"
        headline = "No fixtures scheduled for today"

    leader = performance["leaderboard"][0] if performance["settled_count"] else None
    return {
        "briefing_date": today,
        "headline": headline,
        "tone": briefing_tone,
        "fixtures": fixtures,
        "fixture_count": len(fixtures),
        "value_opportunities": values,
        "positive_value_opportunities": positive,
        "positive_value_count": len(positive),
        "top_opportunity": top,
        "portfolio": portfolio,
        "coach": coach,
        "performance": performance,
        "model_leader": leader,
        "provider_health": {"data": data_diag, "odds": odds_diag, "healthy": system_healthy},
        "active_strategy": active_strategy,
        "decision_engine_active": active_strategy["enforcement_mode"] == "active" and active_strategy["decision_rules_enabled"],
    }
