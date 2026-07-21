from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.paper_trade_service import get_all_paper_trades
from app.templates_config import templates


router = APIRouter()


@router.get("/paper-trades")
def paper_trades_page(request: Request, saved: int = 0):
    db = SessionLocal()

    try:
        trades = get_all_paper_trades(db)

        return templates.TemplateResponse(
            "paper_trades.html",
            {
                "request": request,
                "trades": trades,
                "saved": saved,
            },
        )

    finally:
        db.close()