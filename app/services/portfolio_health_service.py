from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List

from app.models.paper_trade import PaperTrade
from app.services.settings_service import get_settings


SETTLED_STATUSES = {"WON", "LOST", "VOID"}
DECIDED_STATUSES = {"WON", "LOST"}


def _money(value: float) -> float:
    return round(float(value or 0), 2)


def _percentage(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _settled_on_or_after(trade: PaperTrade, start: datetime) -> bool:
    return bool(trade.settled_at and trade.settled_at >= start)


def _group_exposure(
    trades: Iterable[PaperTrade],
    field_name: str,
    bankroll: float,
) -> List[Dict[str, Any]]:
    totals: Dict[str, float] = defaultdict(float)
    counts: Dict[str, int] = defaultdict(int)

    for trade in trades:
        label = str(getattr(trade, field_name, None) or "Unknown")
        totals[label] += float(trade.stake or 0)
        counts[label] += 1

    rows = [
        {
            "label": label,
            "exposure": _money(exposure),
            "exposure_percent": _percentage(exposure, bankroll),
            "positions": counts[label],
        }
        for label, exposure in totals.items()
    ]
    rows.sort(key=lambda row: row["exposure"], reverse=True)
    return rows


def _risk_level(exposure_percent: float, max_daily_risk: float) -> str:
    if max_daily_risk <= 0:
        return "risk" if exposure_percent > 0 else "good"
    if exposure_percent > max_daily_risk:
        return "risk"
    if exposure_percent >= max_daily_risk * 0.75:
        return "warning"
    return "good"


def _health_score(
    exposure_percent: float,
    max_daily_risk: float,
    largest_position_percent: float,
    unsettled_count: int,
) -> int:
    score = 100

    if max_daily_risk > 0:
        utilisation = exposure_percent / max_daily_risk
        if utilisation > 1:
            score -= min(45, int((utilisation - 1) * 35) + 20)
        elif utilisation >= 0.75:
            score -= 15
        elif utilisation >= 0.5:
            score -= 7
    elif exposure_percent > 0:
        score -= 35

    if largest_position_percent > 5:
        score -= min(20, int((largest_position_percent - 5) * 2) + 5)

    if unsettled_count > 10:
        score -= 10
    elif unsettled_count > 5:
        score -= 5

    return max(0, min(100, score))


def _coach_message(data: Dict[str, Any]) -> Dict[str, str]:
    if data["risk_level"] == "risk":
        return {
            "tone": "risk",
            "headline": "Reduce open exposure",
            "message": (
                f"Open stakes equal {data['exposure_percent']}% of bankroll, above "
                f"your {data['max_daily_risk']}% risk limit. Settle existing trades "
                "or reduce new stakes before adding positions."
            ),
        }

    if data["risk_level"] == "warning":
        return {
            "tone": "warning",
            "headline": "Exposure is approaching its limit",
            "message": (
                f"You are using {data['risk_utilisation']}% of the configured daily "
                "risk allowance. Be selective with additional positions."
            ),
        }

    if data["open_positions"] == 0:
        return {
            "tone": "neutral",
            "headline": "No capital is currently exposed",
            "message": (
                "The paper portfolio has no open positions. Review ranked opportunities "
                "and confirm bookmaker value before creating a trade."
            ),
        }

    return {
        "tone": "good",
        "headline": "Portfolio exposure is controlled",
        "message": (
            f"Open exposure is {data['exposure_percent']}% of bankroll and remains "
            f"inside the configured {data['max_daily_risk']}% limit."
        ),
    }


def build_portfolio_health(db) -> Dict[str, Any]:
    settings = get_settings(db)
    starting_bankroll = float(settings.bankroll or 0)
    max_daily_risk = float(settings.max_daily_risk or 0)
    kelly_fraction = float(settings.kelly_fraction or 0)

    trades = db.query(PaperTrade).order_by(PaperTrade.created_at.desc()).all()
    open_trades = [trade for trade in trades if trade.status == "OPEN"]
    settled_trades = [trade for trade in trades if trade.status in SETTLED_STATUSES]
    decided_trades = [trade for trade in trades if trade.status in DECIDED_STATUSES]

    total_profit_loss = _money(sum(float(trade.profit_loss or 0) for trade in settled_trades))
    current_bankroll = _money(starting_bankroll + total_profit_loss)
    open_exposure = _money(sum(float(trade.stake or 0) for trade in open_trades))
    available_bankroll = _money(max(0, current_bankroll - open_exposure))
    exposure_percent = _percentage(open_exposure, current_bankroll)
    risk_utilisation = _percentage(exposure_percent, max_daily_risk)

    total_settled_stake = _money(sum(float(trade.stake or 0) for trade in settled_trades))
    roi = _percentage(total_profit_loss, total_settled_stake)
    wins = sum(1 for trade in decided_trades if trade.status == "WON")
    losses = sum(1 for trade in decided_trades if trade.status == "LOST")
    win_rate = _percentage(wins, wins + losses)
    average_odds = _money(
        sum(float(trade.odds or 0) for trade in trades) / len(trades)
        if trades else 0
    )
    average_stake = _money(
        sum(float(trade.stake or 0) for trade in trades) / len(trades)
        if trades else 0
    )

    now = datetime.utcnow()
    today_start = datetime.combine(date.today(), datetime.min.time())
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    today_profit_loss = _money(sum(
        float(trade.profit_loss or 0)
        for trade in settled_trades
        if _settled_on_or_after(trade, today_start)
    ))
    week_profit_loss = _money(sum(
        float(trade.profit_loss or 0)
        for trade in settled_trades
        if _settled_on_or_after(trade, week_start)
    ))
    month_profit_loss = _money(sum(
        float(trade.profit_loss or 0)
        for trade in settled_trades
        if _settled_on_or_after(trade, month_start)
    ))

    exposure_by_market = _group_exposure(open_trades, "market", current_bankroll)
    exposure_by_player = _group_exposure(open_trades, "selection", current_bankroll)
    exposure_by_bookmaker = _group_exposure(open_trades, "bookmaker", current_bankroll)

    largest_position = max(
        (float(trade.stake or 0) for trade in open_trades),
        default=0.0,
    )
    largest_position_percent = _percentage(largest_position, current_bankroll)
    risk_level = _risk_level(exposure_percent, max_daily_risk)
    health_score = _health_score(
        exposure_percent,
        max_daily_risk,
        largest_position_percent,
        len(open_trades),
    )

    data: Dict[str, Any] = {
        "starting_bankroll": _money(starting_bankroll),
        "current_bankroll": current_bankroll,
        "available_bankroll": available_bankroll,
        "open_exposure": open_exposure,
        "exposure_percent": exposure_percent,
        "risk_utilisation": risk_utilisation,
        "max_daily_risk": round(max_daily_risk, 2),
        "kelly_fraction": round(kelly_fraction, 2),
        "total_profit_loss": total_profit_loss,
        "today_profit_loss": today_profit_loss,
        "week_profit_loss": week_profit_loss,
        "month_profit_loss": month_profit_loss,
        "roi": roi,
        "win_rate": win_rate,
        "average_odds": average_odds,
        "average_stake": average_stake,
        "open_positions": len(open_trades),
        "settled_positions": len(settled_trades),
        "won_positions": wins,
        "lost_positions": losses,
        "largest_position": _money(largest_position),
        "largest_position_percent": largest_position_percent,
        "risk_level": risk_level,
        "health_score": health_score,
        "exposure_by_market": exposure_by_market,
        "exposure_by_player": exposure_by_player,
        "exposure_by_bookmaker": exposure_by_bookmaker,
    }
    data["coach"] = _coach_message(data)
    return data
