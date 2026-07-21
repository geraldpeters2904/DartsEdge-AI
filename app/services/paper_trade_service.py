from app.models.paper_trade import PaperTrade


def get_all_paper_trades(db):
    return (
        db.query(PaperTrade)
        .order_by(PaperTrade.created_at.desc())
        .all()
    )