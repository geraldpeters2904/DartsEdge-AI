from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.db import SessionLocal
from app.models.player import Player
from app.services.kelly_service import calculate_kelly_stake
from app.services.prediction_pipeline import build_prediction
from app.services.prediction_audit_service import create_prediction_audit
from app.services.prediction_storage_service import save_prediction
from app.services.settings_service import get_settings
from app.services.trade_rating_service import calculate_trade_rating
from app.services.value_bet_service import calculate_value_bet
from app.services.value_scanner_service import rank_opportunities
from app.templates_config import templates


router = APIRouter()


def get_players(db):
    return [
        {"name": player.name}
        for player in db.query(Player).order_by(Player.name.asc()).all()
    ]


def _setting(settings, name: str, default):
    value = getattr(settings, name, None)
    return default if value is None else value


@router.get("/predict")
def predict_page(request: Request):
    db = SessionLocal()
    try:
        return templates.TemplateResponse(
            "predict.html",
            {
                "request": request,
                "players": get_players(db),
                "selected_player_a": None,
                "selected_player_b": None,
            },
        )
    finally:
        db.close()


@router.get("/predict-v2")
def predict_v2_page(
    request: Request,
    player_a: Optional[str] = None,
    player_b: Optional[str] = None,
):
    db = SessionLocal()
    try:
        return templates.TemplateResponse(
            "predict_v2.html",
            {
                "request": request,
                "players": get_players(db),
                "selected_player_a": player_a,
                "selected_player_b": player_b,
            },
        )
    finally:
        db.close()


@router.get("/value-bet")
def value_bet_analysis(
    request: Request,
    probability: float,
    bookmaker_odds: float,
):
    db = SessionLocal()
    try:
        settings = get_settings(db)

        if probability <= 0 or probability > 100:
            return templates.TemplateResponse(
                "value_bets.html",
                {
                    "request": request,
                    "probability": probability,
                    "bookmaker_odds": bookmaker_odds,
                    "error": "Probability must be between 0 and 100.",
                },
                status_code=400,
            )

        if bookmaker_odds <= 1:
            return templates.TemplateResponse(
                "value_bets.html",
                {
                    "request": request,
                    "probability": probability,
                    "bookmaker_odds": bookmaker_odds,
                    "error": "Bookmaker odds must be greater than 1.00.",
                },
                status_code=400,
            )

        value_bet = calculate_value_bet(
            probability / 100,
            bookmaker_odds,
            minimum_edge=_setting(settings, "minimum_edge", 5.0),
            minimum_confidence=_setting(
                settings, "minimum_confidence", 60.0
            ),
        )

        return templates.TemplateResponse(
            "value_bets.html",
            {
                "request": request,
                "probability": probability,
                "bookmaker_odds": bookmaker_odds,
                "value_bet": value_bet,
            },
        )
    finally:
        db.close()


@router.get("/predict-v2-result")
def predict_v2_result(
    request: Request,
    player_a: Optional[str] = None,
    player_b: Optional[str] = None,
    bookmaker_odds: Optional[float] = None,
):
    if not player_a or not player_b:
        return RedirectResponse(url="/predict-v2", status_code=303)

    db = SessionLocal()
    try:
        players = get_players(db)
        settings = get_settings(db)

        if player_a == player_b:
            return templates.TemplateResponse(
                "predict_v2.html",
                {
                    "request": request,
                    "players": players,
                    "selected_player_a": player_a,
                    "selected_player_b": player_b,
                    "error": "Please select two different players.",
                },
                status_code=400,
            )

        result = build_prediction(db, player_a, player_b)

        if not result:
            return templates.TemplateResponse(
                "predict_v2.html",
                {
                    "request": request,
                    "players": players,
                    "selected_player_a": player_a,
                    "selected_player_b": player_b,
                    "error": "One or both players were not found.",
                },
                status_code=404,
            )

        saved_prediction = save_prediction(db, result)
        result["prediction_id"] = saved_prediction.id
        audit_record = create_prediction_audit(db, result, prediction_id=saved_prediction.id, source="prediction-centre")
        result["audit_uuid"] = audit_record.audit_uuid

        bankroll = _setting(settings, "bankroll", 1000.0)
        kelly_fraction = _setting(settings, "kelly_fraction", 0.25)
        max_daily_risk = _setting(settings, "max_daily_risk", 5.0)

        opportunities = result.get("trading_opportunities", [])

        for opportunity in opportunities:
            rating = calculate_trade_rating(opportunity)
            kelly = calculate_kelly_stake(
                probability=opportunity["probability"],
                bookmaker_odds=opportunity["minimum_odds"],
                bankroll=bankroll,
                fraction=kelly_fraction,
                max_daily_risk_percent=max_daily_risk,
            )

            opportunity["trade_score"] = rating["score"]
            opportunity["trade_stars"] = rating["stars"]
            opportunity["trade_grade"] = rating["grade"]
            opportunity["kelly_percent"] = kelly["kelly_percent"]
            opportunity["recommended_stake"] = kelly["recommended_stake"]
            opportunity["expected_value"] = kelly["expected_value_percent"]
            opportunity["risk_level"] = kelly["risk_level"]
            opportunity["prediction_id"] = saved_prediction.id

        result["trading_opportunities"] = rank_opportunities(opportunities)
        result["value_bet"] = None

        if bookmaker_odds is not None:
            if bookmaker_odds <= 1:
                return templates.TemplateResponse(
                    "predict_v2.html",
                    {
                        "request": request,
                        "players": players,
                        "result": result,
                        "selected_player_a": player_a,
                        "selected_player_b": player_b,
                        "error": "Bookmaker odds must be greater than 1.00.",
                    },
                    status_code=400,
                )

            recommended_selection = result["recommendation"]["selection"]
            selected_probability = (
                result["win_prob_a"]
                if recommended_selection == player_a
                else result["win_prob_b"]
            )

            result["value_bet"] = calculate_value_bet(
                selected_probability,
                bookmaker_odds,
                minimum_edge=_setting(settings, "minimum_edge", 5.0),
                minimum_confidence=_setting(
                    settings, "minimum_confidence", 60.0
                ),
            )

        return templates.TemplateResponse(
            "predict_v2.html",
            {
                "request": request,
                "players": players,
                "result": result,
                "selected_player_a": player_a,
                "selected_player_b": player_b,
            },
        )
    finally:
        db.close()


@router.post("/save-prediction")
async def save_prediction_route(request: Request):
    form = await request.form()
    player_a = form.get("player_a")
    player_b = form.get("player_b")

    if not player_a or not player_b:
        return {"error": "Player names not supplied."}

    db = SessionLocal()
    try:
        result = build_prediction(db, player_a, player_b)
        if not result:
            return {"error": "Prediction could not be generated."}

        saved = save_prediction(db, result)
        create_prediction_audit(db, result, prediction_id=saved.id, source="save-prediction")
        return RedirectResponse(url="/prediction-history", status_code=303)
    finally:
        db.close()


@router.get("/predict-ui")
def predict_ui(
    request: Request,
    player_a: Optional[str] = None,
    player_b: Optional[str] = None,
):
    if not player_a or not player_b:
        return RedirectResponse(url="/predict", status_code=303)

    db = SessionLocal()
    try:
        players = get_players(db)

        if player_a == player_b:
            return templates.TemplateResponse(
                "predict.html",
                {
                    "request": request,
                    "players": players,
                    "selected_player_a": player_a,
                    "selected_player_b": player_b,
                    "error": "Please select two different players.",
                },
                status_code=400,
            )

        result = build_prediction(db, player_a, player_b)

        if not result:
            return templates.TemplateResponse(
                "predict.html",
                {
                    "request": request,
                    "players": players,
                    "selected_player_a": player_a,
                    "selected_player_b": player_b,
                    "error": "One or both players were not found.",
                },
                status_code=404,
            )

        return templates.TemplateResponse(
            "predict.html",
            {
                "request": request,
                "players": players,
                "result": result,
                "selected_player_a": player_a,
                "selected_player_b": player_b,
            },
        )
    finally:
        db.close()


@router.get("/value-bet-page")
def value_bet_page(
    request: Request,
    probability: Optional[float] = None,
    selection: Optional[str] = None,
    opponent: Optional[str] = None,
):
    return templates.TemplateResponse(
        "value_bets.html",
        {
            "request": request,
            "probability": probability,
            "selection": selection,
            "opponent": opponent,
        },
    )
