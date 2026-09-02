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


def get_portfolio_summary(
    db,
    starting_bankroll=5000.00,
):
    trades = db.query(PaperTrade).all()

    settled_trades = [
        trade
        for trade in trades
        if trade.status in VALID_SETTLEMENT_STATUSES
    ]

    total_profit_loss = round(
        sum(
            float(trade.profit_loss or 0)
            for trade in settled_trades
        ),
        2,
    )

    settled_stake = round(
        sum(
            float(trade.stake or 0)
            for trade in settled_trades
        ),
        2,
    )

    current_bankroll = round(
        float(starting_bankroll) + total_profit_loss,
        2,
    )

    if settled_stake > 0:
        roi = round(
            (total_profit_loss / settled_stake) * 100,
            2,
        )
    else:
        roi = 0.0

    profit_values = [
        float(trade.profit_loss or 0)
        for trade in settled_trades
    ]

    biggest_win = round(
        max(
            [
                value
                for value in profit_values
                if value > 0
            ],
            default=0.0,
        ),
        2,
    )

    biggest_loss = round(
        min(
            [
                value
                for value in profit_values
                if value < 0
            ],
            default=0.0,
        ),
        2,
    )

    return {
        "starting_bankroll": round(
            float(starting_bankroll),
            2,
        ),
        "current_bankroll": current_bankroll,
        "total_profit_loss": total_profit_loss,
        "portfolio_roi": roi,
        "settled_stake": settled_stake,
        "biggest_win": biggest_win,
        "biggest_loss": biggest_loss,
    }


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


def _settle_trade_as_win_or_loss(
    trade,
    *,
    winning_selection,
):
    stake = float(trade.stake or 0)
    odds = float(trade.odds or 0)

    if trade.selection == winning_selection:
        trade.status = "WON"
        trade.profit_loss = round(
            stake * (odds - 1),
            2,
        )
    else:
        trade.status = "LOST"
        trade.profit_loss = round(
            -stake,
            2,
        )

    trade.settled_at = datetime.utcnow()


def settle_open_match_winner_trades_for_fixture(
    db,
    fixture_id,
):
    """
    Settle eligible OPEN Match Winner paper trades for one completed fixture.

    This function deliberately does not commit. Transaction ownership belongs
    to the caller so settlement can participate atomically in canonical result
    persistence.
    """
    from app.models.match import Match

    match = (
        db.query(Match)
        .filter(Match.id == fixture_id)
        .first()
    )

    if (
        match is None
        or match.status != "completed"
        or not match.winner
    ):
        return []

    trades = (
        db.query(PaperTrade)
        .filter(
            PaperTrade.fixture_id == fixture_id,
            PaperTrade.status == "OPEN",
            PaperTrade.market == "Match Winner",
        )
        .all()
    )

    settled = []

    for trade in trades:
        if trade.selection not in {
            match.player_a,
            match.player_b,
        }:
            continue

        _settle_trade_as_win_or_loss(
            trade,
            winning_selection=match.winner,
        )
        settled.append(trade)

    if settled:
        db.flush()

    return settled


def settle_open_first_180_trades_for_fixture(
    db,
    fixture_id,
):
    """
    Settle eligible OPEN First 180 paper trades for one completed fixture.

    Missing First 180 result data is not inferred. Such trades remain OPEN.
    This function deliberately does not commit.
    """
    from app.models.match import Match

    match = (
        db.query(Match)
        .filter(Match.id == fixture_id)
        .first()
    )

    if (
        match is None
        or match.status != "completed"
        or not match.first_180_player
        or match.first_180_player not in {
            match.player_a,
            match.player_b,
        }
    ):
        return []

    trades = (
        db.query(PaperTrade)
        .filter(
            PaperTrade.fixture_id == fixture_id,
            PaperTrade.status == "OPEN",
            PaperTrade.market == "First 180",
        )
        .all()
    )

    settled = []

    for trade in trades:
        if trade.selection not in {
            match.player_a,
            match.player_b,
        }:
            continue

        _settle_trade_as_win_or_loss(
            trade,
            winning_selection=match.first_180_player,
        )
        settled.append(trade)

    if settled:
        db.flush()

    return settled


def settle_open_trades_for_fixture(
    db,
    fixture_id,
):
    """
    Settle all currently supported OPEN markets for one exact fixture.

    Transaction ownership remains with the caller.
    """
    settled = []
    settled.extend(
        settle_open_match_winner_trades_for_fixture(
            db,
            fixture_id,
        )
    )
    settled.extend(
        settle_open_first_180_trades_for_fixture(
            db,
            fixture_id,
        )
    )
    return settled
