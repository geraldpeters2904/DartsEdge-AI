from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.db import SessionLocal
from app.models.paper_trade import PaperTrade
from app.models.prediction import Prediction
from app.templates_config import templates


router = APIRouter()


@router.get("/paper-trades/new/{prediction_id}")
def new_paper_trade(request: Request, prediction_id: int):
    db = SessionLocal()

    try:
        prediction = (
            db.query(Prediction)
            .filter(Prediction.id == prediction_id)
            .first()
        )

        if prediction is None:
            raise HTTPException(
                status_code=404,
                detail="Prediction not found",
            )

        return templates.TemplateResponse(
            "new_paper_trade.html",
            {
                "request": request,
                "prediction": prediction,
            },
        )

    finally:
        db.close()


@router.post("/paper-trades/new")
def save_new_paper_trade(
    prediction_id: int = Form(...),
    market: str = Form(...),
    selection: str = Form(...),
    odds: float = Form(...),
    stake: float = Form(...),
    bookmaker: str = Form("Paper Trade"),
):
    db = SessionLocal()

    try:
        prediction = (
            db.query(Prediction)
            .filter(Prediction.id == prediction_id)
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

        if selection not in valid_selections:
            raise HTTPException(
                status_code=400,
                detail="Invalid trade selection",
            )

        if odds <= 1:
            raise HTTPException(
                status_code=400,
                detail="Decimal odds must be greater than 1.00",
            )

        if stake <= 0:
            raise HTTPException(
                status_code=400,
                detail="Stake must be greater than zero",
            )

        trade = PaperTrade(
            prediction_id=prediction.id,
            market=market,
            selection=selection,
            bookmaker=bookmaker.strip() or "Paper Trade",
            odds=odds,
            stake=stake,
            status="OPEN",
        )

        db.add(trade)
        db.commit()

        return RedirectResponse(
            url="/paper-trades?saved=1",
            status_code=303,
        )

    except:
        db.rollback()
        raise

    finally:
        db.close()