from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.db import SessionLocal
from app.models.paper_trade import PaperTrade
from app.models.prediction import Prediction
from app.services.decision_engine_service import decide, summary
from app.services.expected_value_service import assess_value
from app.services.paper_trade_service import (
    get_all_paper_trades,
    open_trade_exists_for_match,
    settle_paper_trade,
)
from app.services.portfolio_health_service import build_portfolio_health
from app.services.settings_service import get_settings
from app.templates_config import templates


router = APIRouter()


class PaperTradeCreate(BaseModel):
    prediction_id: int
    market: str
    decision_market: str
    selection: str
    odds: float
    model_probability: float
    confidence_percent: float
    sample_size: int = Field(default=0, ge=0)
    competition: str = ""
    bookmaker: str = "Trading Opportunities"


class TradingOpportunityEvaluation(BaseModel):
    prediction_id: int
    market: str
    selection: str
    odds: float
    model_probability: float
    confidence_percent: float
    sample_size: int = Field(default=0, ge=0)
    competition: str = ""
    bookmaker: str = "Trading Opportunities"


class PaperTradeSettlement(BaseModel):
    status: str


@router.get("/paper-trades")
def paper_trades_page(request: Request, saved: int = 0):
    db = SessionLocal()

    try:
        trades = get_all_paper_trades(db)

        prediction_ids = {
            trade.prediction_id
            for trade in trades
            if trade.prediction_id is not None
        }
        predictions = (
            db.query(Prediction)
            .filter(Prediction.id.in_(prediction_ids))
            .all()
            if prediction_ids
            else []
        )
        predictions_by_id = {
            prediction.id: prediction
            for prediction in predictions
        }

        return templates.TemplateResponse(
            "paper_trades.html",
            {
                "request": request,
                "trades": trades,
                "predictions_by_id": predictions_by_id,
                "saved": saved,
            },
        )

    finally:
        db.close()


@router.post("/api/trading-opportunities/evaluate")
def evaluate_trading_opportunity(
    payload: TradingOpportunityEvaluation,
):
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

        settings = get_settings(db)
        assessment = assess_value(
            model_probability=payload.model_probability,
            decimal_odds=payload.odds,
            bookmaker=payload.bookmaker,
            bankroll=settings.bankroll,
            kelly_fraction=settings.kelly_fraction,
            max_daily_risk_percent=settings.max_daily_risk,
            minimum_edge_percent=settings.minimum_edge,
        )
        portfolio = build_portfolio_health(db)
        decision_engine = decide(
            db,
            official_decision=assessment.decision,
            official_stake=assessment.recommended_stake,
            model_probability=assessment.model_probability,
            confidence_percent=payload.confidence_percent,
            expected_value_percent=assessment.expected_value_percent,
            edge_percent=assessment.edge_percent,
            decimal_odds=assessment.decimal_odds,
            bankroll=settings.bankroll,
            market=payload.market,
            competition=payload.competition,
            sample_size=payload.sample_size,
            portfolio_exposure_percent=portfolio.get(
                "exposure_percent"
            ),
        )

        return {
            "success": True,
            "model_probability": assessment.model_probability,
            "decimal_odds": assessment.decimal_odds,
            "fair_odds": assessment.fair_odds,
            "edge_percent": assessment.edge_percent,
            "expected_value_percent": (
                assessment.expected_value_percent
            ),
            "kelly_percent": assessment.kelly_percent,
            "raw_kelly_stake": assessment.recommended_stake,
            "risk_level": assessment.risk_level,
            "decision_engine": summary(decision_engine),
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
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

        if open_trade_exists_for_match(
            db,
            prediction,
            payload.market,
            payload.selection,
        ):
            return {
                "success": True,
                "already_exists": True,
                "message": (
                    "An OPEN paper trade already exists "
                    "for this market."
                ),
            }

        settings = get_settings(db)
        assessment = assess_value(
            model_probability=payload.model_probability,
            decimal_odds=payload.odds,
            bookmaker=payload.bookmaker,
            bankroll=settings.bankroll,
            kelly_fraction=settings.kelly_fraction,
            max_daily_risk_percent=settings.max_daily_risk,
            minimum_edge_percent=settings.minimum_edge,
        )
        portfolio = build_portfolio_health(db)
        decision_engine = decide(
            db,
            official_decision=assessment.decision,
            official_stake=assessment.recommended_stake,
            model_probability=assessment.model_probability,
            confidence_percent=payload.confidence_percent,
            expected_value_percent=assessment.expected_value_percent,
            edge_percent=assessment.edge_percent,
            decimal_odds=assessment.decimal_odds,
            bankroll=settings.bankroll,
            market=payload.decision_market,
            competition=payload.competition,
            sample_size=payload.sample_size,
            portfolio_exposure_percent=portfolio.get(
                "exposure_percent"
            ),
        )

        trade = PaperTrade(
            prediction_id=prediction.id,
            market=payload.market.strip(),
            selection=payload.selection,
            bookmaker=(
                payload.bookmaker.strip()
                or "Trading Opportunities"
            ),
            odds=payload.odds,
            stake=decision_engine.effective_stake,
            model_probability=assessment.model_probability,
            expected_value=assessment.expected_value_percent,
            suggested_stake=assessment.recommended_stake,
            strategy_name=decision_engine.strategy_name,
            status="OPEN",
        )

        db.add(trade)
        db.commit()
        db.refresh(trade)

        return {
            "success": True,
            "already_exists": False,
            "trade_id": trade.id,
            "message": "Paper trade saved successfully",
        }

    except HTTPException:
        db.rollback()
        raise

    except ValueError as error:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to save paper trade",
        )

    finally:
        db.close()


@router.post("/api/paper-trades/{trade_id}/settle")
def settle_trade(
    trade_id: int,
    payload: PaperTradeSettlement,
):
    db = SessionLocal()

    try:
        trade = settle_paper_trade(
            db,
            trade_id,
            payload.status,
        )

        if trade is None:
            raise HTTPException(
                status_code=404,
                detail="Paper trade not found",
            )

        return {
            "success": True,
            "trade_id": trade.id,
            "status": trade.status,
            "profit_loss": trade.profit_loss,
        }

    except ValueError as error:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to settle paper trade",
        )

    finally:
        db.close()
