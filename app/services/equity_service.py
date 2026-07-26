from app.models.paper_trade import PaperTrade


def get_equity_curve(db, starting_bankroll=5000.0):
    trades = (
        db.query(PaperTrade)
        .filter(PaperTrade.status.in_(["WON", "LOST"]))
        .order_by(PaperTrade.id)
        .all()
    )

    bankroll = starting_bankroll
    curve = []

    for trade in trades:
        profit_loss = trade.profit_loss or 0.0
        bankroll += profit_loss

        curve.append(
            {
                "trade": trade.id,
                "bankroll": round(bankroll, 2),
                "profit_loss": round(profit_loss, 2),
                "selection": trade.selection,
            }
        )

    return curve