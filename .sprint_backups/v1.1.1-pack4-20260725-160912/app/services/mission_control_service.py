from datetime import date
from typing import Any, Dict, List

from app.models.paper_trade import PaperTrade
from app.services.dashboard_service import build_dashboard_data
from app.services.opportunity_ranking_service import build_ranked_opportunities
from app.services.portfolio_health_service import build_portfolio_health


def _status(label: str, value: float, good: float, warning: float) -> Dict[str, Any]:
    if value >= good:
        level = "good"
    elif value >= warning:
        level = "warning"
    else:
        level = "risk"

    return {
        "label": label,
        "value": value,
        "level": level,
    }


def _build_alerts(dashboard: Dict[str, Any]) -> List[Dict[str, str]]:
    alerts = []

    if dashboard["results_awaiting"]:
        alerts.append(
            {
                "level": "warning",
                "title": "Results awaiting update",
                "message": (
                    f"{len(dashboard['results_awaiting'])} previous fixture(s) "
                    "still need a result."
                ),
                "url": "/fixtures",
                "action": "Review fixtures",
            }
        )

    if dashboard["database_health"] < 80:
        alerts.append(
            {
                "level": "risk",
                "title": "Data quality needs attention",
                "message": (
                    f"Database health is {dashboard['database_health']}%. "
                    "Prediction quality may improve after missing data is resolved."
                ),
                "url": "/data-quality",
                "action": "Open data quality",
            }
        )

    if dashboard["open_paper_trades"] > 0:
        alerts.append(
            {
                "level": "info",
                "title": "Open paper positions",
                "message": (
                    f"{dashboard['open_paper_trades']} paper trade(s) are currently open."
                ),
                "url": "/paper-trades",
                "action": "Review portfolio",
            }
        )

    if not alerts:
        alerts.append(
            {
                "level": "good",
                "title": "No urgent actions",
                "message": "Mission Control has not detected any immediate issues.",
                "url": "/dashboard",
                "action": "View dashboard",
            }
        )

    return alerts[:4]


def _build_ai_coach(dashboard: Dict[str, Any]) -> Dict[str, str]:
    best_bet = dashboard.get("best_bet")

    if dashboard["database_health"] < 70:
        return {
            "tone": "risk",
            "headline": "Improve the data before increasing activity",
            "message": (
                "The database health score is below the preferred operating range. "
                "Resolve missing or incomplete records before relying on larger stakes."
            ),
            "action": "Review data quality",
            "url": "/data-quality",
        }

    if best_bet:
        return {
            "tone": "good",
            "headline": f"Top model lean: {best_bet['selection']}",
            "message": (
                f"The strongest current model signal is {best_bet['selection']} at "
                f"{best_bet['probability']}% probability. Check available odds before "
                "treating it as a value opportunity."
            ),
            "action": "Open value scanner",
            "url": "/value-bet-page",
        }

    if dashboard["today_fixture_count"]:
        return {
            "tone": "warning",
            "headline": "Fixtures are available but no ranked bets are ready",
            "message": (
                "Review today's fixtures in Prediction Centre to generate current "
                "analysis and opportunity data."
            ),
            "action": "Analyse fixtures",
            "url": "/predict-v2",
        }

    return {
        "tone": "neutral",
        "headline": "No immediate betting action recommended",
        "message": (
            "There are no ranked opportunities on the board. Import or add fixtures, "
            "then run the prediction workflow."
        ),
        "action": "Open fixtures",
        "url": "/fixtures",
    }


def build_mission_control_data(db) -> Dict[str, Any]:
    dashboard = build_dashboard_data(db)
    ranked_opportunities = build_ranked_opportunities(db, limit=5)
    portfolio_health = build_portfolio_health(db)

    model_health = [
        _status("Winner accuracy", dashboard["winner_accuracy"], 65, 55),
        _status("Database health", dashboard["database_health"], 85, 70),
        _status("Portfolio health", portfolio_health["health_score"], 80, 60),
    ]

    return {
        **dashboard,
        "mission_control_date": date.today(),
        "ranked_opportunities": ranked_opportunities,
        "opportunity_count": len(ranked_opportunities),
        "open_stake": portfolio_health["open_exposure"],
        "exposure_percent": portfolio_health["exposure_percent"],
        "portfolio_health": portfolio_health,
        "model_health": model_health,
        "alerts": _build_alerts(dashboard),
        "ai_coach": portfolio_health["coach"],
    }
