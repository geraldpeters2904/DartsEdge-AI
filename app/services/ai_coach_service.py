from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from app.services.dashboard_service import build_dashboard_data
from app.services.opportunity_ranking_service import build_ranked_opportunities
from app.services.portfolio_health_service import build_portfolio_health


TONE_ORDER = {"risk": 0, "warning": 1, "good": 2, "neutral": 3}


def _advice(
    *,
    priority: int,
    tone: str,
    category: str,
    title: str,
    message: str,
    action: str,
    url: str,
) -> Dict[str, Any]:
    return {
        "priority": priority,
        "tone": tone,
        "category": category,
        "title": title,
        "message": message,
        "action": action,
        "url": url,
    }


def _portfolio_advice(portfolio: Dict[str, Any]) -> List[Dict[str, Any]]:
    advice: List[Dict[str, Any]] = []

    if portfolio["risk_level"] == "risk":
        advice.append(_advice(
            priority=100,
            tone="risk",
            category="Risk control",
            title="Pause new positions",
            message=(
                f"Open exposure is {portfolio['exposure_percent']}% of bankroll, above "
                f"the configured {portfolio['max_daily_risk']}% limit. Settle or reduce "
                "existing positions before adding another trade."
            ),
            action="Review portfolio",
            url="/portfolio-health",
        ))
    elif portfolio["risk_level"] == "warning":
        advice.append(_advice(
            priority=85,
            tone="warning",
            category="Risk control",
            title="Be selective with new stakes",
            message=(
                f"The portfolio is using {portfolio['risk_utilisation']}% of its daily "
                "risk allowance. Only consider the strongest confirmed-value positions."
            ),
            action="Review exposure",
            url="/portfolio-health",
        ))
    elif portfolio["open_positions"] > 0:
        advice.append(_advice(
            priority=45,
            tone="good",
            category="Risk control",
            title="Exposure remains controlled",
            message=(
                f"Open exposure is {portfolio['exposure_percent']}% of bankroll across "
                f"{portfolio['open_positions']} position(s), inside the configured limit."
            ),
            action="View portfolio",
            url="/portfolio-health",
        ))
    else:
        advice.append(_advice(
            priority=35,
            tone="neutral",
            category="Risk control",
            title="No capital is currently exposed",
            message=(
                "There are no open paper trades. Confirm bookmaker value before creating "
                "a new position."
            ),
            action="Review opportunities",
            url="/opportunities",
        ))

    if portfolio["largest_position_percent"] >= 5:
        advice.append(_advice(
            priority=80,
            tone="warning",
            category="Concentration",
            title="Largest stake is concentrated",
            message=(
                f"The largest open position represents {portfolio['largest_position_percent']}% "
                "of bankroll. Consider smaller stake sizes to reduce single-result risk."
            ),
            action="Inspect open trades",
            url="/paper-trades",
        ))

    return advice


def _opportunity_advice(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    advice: List[Dict[str, Any]] = []
    confirmed = [item for item in opportunities if item.get("is_value_confirmed")]
    odds_required = [item for item in opportunities if item.get("market_odds") is None]

    if confirmed:
        best = confirmed[0]
        advice.append(_advice(
            priority=75,
            tone="good",
            category="Opportunity",
            title=f"Confirmed value: {best['selection']}",
            message=(
                f"The top confirmed-value signal has a {best['probability']}% model "
                f"probability and a {best['edge_percent']}% edge at available odds. "
                "Apply your staking limits before acting."
            ),
            action="Open ranking",
            url="/opportunities",
        ))
    elif odds_required:
        best = odds_required[0]
        minimum = best.get("minimum_odds") or best.get("fair_odds")
        minimum_text = f" around {minimum:.2f} or better" if minimum else " before acting"
        advice.append(_advice(
            priority=65,
            tone="warning",
            category="Opportunity",
            title=f"Check odds for {best['selection']}",
            message=(
                f"This is the strongest current model signal at {best['probability']}%. "
                f"It is not yet a confirmed value bet; look for market odds{minimum_text}."
            ),
            action="Check opportunities",
            url="/opportunities",
        ))
    else:
        advice.append(_advice(
            priority=40,
            tone="neutral",
            category="Opportunity",
            title="No actionable value signal",
            message=(
                "No ranked opportunity currently combines a strong model signal with "
                "acceptable market value. Passing is a valid decision."
            ),
            action="View ranking",
            url="/opportunities",
        ))

    return advice


def _data_advice(dashboard: Dict[str, Any]) -> List[Dict[str, Any]]:
    advice: List[Dict[str, Any]] = []

    if dashboard["database_health"] < 70:
        advice.append(_advice(
            priority=95,
            tone="risk",
            category="Data quality",
            title="Improve data before increasing stakes",
            message=(
                f"Database health is {dashboard['database_health']}%. Missing or incomplete "
                "records can weaken predictions, so resolve data issues first."
            ),
            action="Review data quality",
            url="/data-quality",
        ))
    elif dashboard["database_health"] < 85:
        advice.append(_advice(
            priority=60,
            tone="warning",
            category="Data quality",
            title="Data quality can be improved",
            message=(
                f"Database health is {dashboard['database_health']}%. The model can operate, "
                "but completing missing records should improve reliability."
            ),
            action="Review data quality",
            url="/data-quality",
        ))

    awaiting = len(dashboard.get("results_awaiting") or [])
    if awaiting:
        advice.append(_advice(
            priority=70,
            tone="warning",
            category="Operations",
            title="Update outstanding fixture results",
            message=(
                f"{awaiting} previous fixture(s) still need a result. Updating them keeps "
                "accuracy reporting and model evaluation current."
            ),
            action="Update fixtures",
            url="/fixtures",
        ))

    if dashboard["prediction_count"] < 20:
        advice.append(_advice(
            priority=30,
            tone="neutral",
            category="Model evidence",
            title="Build a larger prediction sample",
            message=(
                f"Only {dashboard['prediction_count']} prediction(s) are recorded. Treat early "
                "accuracy and ROI figures as provisional until the sample grows."
            ),
            action="Open Prediction Centre",
            url="/predict-v2",
        ))

    return advice


def build_ai_coach_data(db) -> Dict[str, Any]:
    dashboard = build_dashboard_data(db)
    portfolio = build_portfolio_health(db)
    opportunities = build_ranked_opportunities(db, limit=20)

    recommendations = (
        _portfolio_advice(portfolio)
        + _opportunity_advice(opportunities)
        + _data_advice(dashboard)
    )
    recommendations.sort(
        key=lambda item: (-item["priority"], TONE_ORDER.get(item["tone"], 9))
    )

    primary = recommendations[0]
    secondary = recommendations[1:6]
    urgent_count = sum(1 for item in recommendations if item["tone"] == "risk")
    warning_count = sum(1 for item in recommendations if item["tone"] == "warning")
    confirmed_value_count = sum(
        1 for item in opportunities if item.get("is_value_confirmed")
    )

    return {
        "coach_date": date.today(),
        "primary": primary,
        "recommendations": recommendations,
        "secondary_recommendations": secondary,
        "urgent_count": urgent_count,
        "warning_count": warning_count,
        "recommendation_count": len(recommendations),
        "confirmed_value_count": confirmed_value_count,
        "ranked_opportunity_count": len(opportunities),
        "portfolio": portfolio,
        "dashboard": dashboard,
    }
