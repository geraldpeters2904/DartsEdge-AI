from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.db import SessionLocal
from app.models.paper_trade import PaperTrade
from app.models.prediction import Prediction
from app.services.paper_trade_service import get_all_paper_trades
from app.templates_config import templates


router = APIRouter()


class PaperTradeCreate(BaseModel):
    prediction_id: int
    market: str
    selection: str
    odds: float
    stake: float = Field(default=1.0, gt=0)
    bookmaker: str = "Trading Opportunities"


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


@router.post("/api/paper-trades")
def create_paper_trade(payload: PaperTradeCreate):
    db = SessionLocal()

    try:
        prediction = (
            db.query(Prediction)
            .filter(Prediction.id == payload.prediction_id)
            .first()
        )

        if prediction is None:
            raise HTTPException(
                status_code=404,
                detail="Prediction not found",
            )

        valid_selections = {
            prediction.player_a,
            prediction.player_b,
        }

        if payload.selection not in valid_selections:
            raise HTTPException(
                status_code=400,
                detail="Invalid trade selection",
            )

        if payload.odds <= 1:
            raise HTTPException(
                status_code=400,
                detail="Decimal odds must be greater than 1.00",
            )

        trade = PaperTrade(
            prediction_id=prediction.id,
            market=payload.market.strip(),
            selection=payload.selection,
            bookmaker=payload.bookmaker.strip()
            or "Trading Opportunities",
            odds=payload.odds,
            stake=payload.stake,
            status="OPEN",
        )

        db.add(trade)
        db.commit()
        db.refresh(trade)

        return {
            "success": True,
            "trade_id": trade.id,
            "message": "Paper trade saved successfully",
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to save paper trade",
        )

    finally:
        db.close()