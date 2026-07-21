from datetime import datetime

from app.models.paper_trade import PaperTrade
from app.models.prediction import Prediction


VALID_SETTLEMENT_STATUSES = {
    "WON",
    "LOST",
    "VOID",
}


def get_all_paper_trades(db):
    return (
        db.query(PaperTrade)
        .order_by(PaperTrade.created_at.desc())
        .all()
    )


def paper_trade_exists(
    db,
    prediction_id,
    market,
    selection,
):
    return (
        db.query(PaperTrade)
        .filter(
            PaperTrade.prediction_id == prediction_id,
            PaperTrade.market == market,
            PaperTrade.selection == selection,
        )
        .first()
        is not None
    )


def open_trade_exists_for_match(
    db,
    prediction,
    market,
    selection,
):
    return (
        db.query(PaperTrade)
        .join(
            Prediction,
            PaperTrade.prediction_id == Prediction.id,
        )
        .filter(
            PaperTrade.status == "OPEN",
            PaperTrade.market == market,
            PaperTrade.selection == selection,
        )
        .filter(
            (
                (Prediction.player_a == prediction.player_a)
                & (Prediction.player_b == prediction.player_b)
            )
            |
            (
                (Prediction.player_a == prediction.player_b)
                & (Prediction.player_b == prediction.player_a)
            )
        )
        .first()
        is not None
    )


def settle_paper_trade(
    db,
    trade_id,
    status,
):
    status = status.strip().upper()

    if status not in VALID_SETTLEMENT_STATUSES:
        raise ValueError(
            "Status must be WON, LOST or VOID"
        )

    trade = (
        db.query(PaperTrade)
        .filter(PaperTrade.id == trade_id)
        .first()
    )

    if trade is None:
        return None

    if trade.status != "OPEN":
        raise ValueError(
            "Only OPEN paper trades can be settled"
        )

    stake = float(trade.stake or 0)
    odds = float(trade.odds or 0)

    if status == "WON":
        profit_loss = stake * (odds - 1)

    elif status == "LOST":
        profit_loss = -stake

    else:
        profit_loss = 0

    trade.status = status
    trade.profit_loss = round(
        profit_loss,
        2,
    )
    trade.settled_at = datetime.utcnow()

    db.commit()
    db.refresh(trade)

    return trade