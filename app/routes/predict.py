from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.models.player import Player
from app.services.prediction_pipeline import build_prediction
from app.services.value_bet_service import calculate_value_bet
from app.templates_config import templates


router = APIRouter()


def get_players(db):
    return [
        {"name": player.name}
        for player in (
            db.query(Player)
            .order_by(Player.name.asc())
            .all()
        )
    ]


@router.get("/predict")
def predict_page(request: Request):
    db = SessionLocal()

    try:
        players = get_players(db)

        return templates.TemplateResponse(
            "predict.html",
            {
                "request": request,
                "players": players,
                "selected_player_a": None,
                "selected_player_b": None,
            },
        )

    finally:
        db.close()


@router.get("/predict-v2")
def predict_v2_page(
    request: Request,
    player_a: str = None,
    player_b: str = None,
):
    db = SessionLocal()

    try:
        players = get_players(db)

        return templates.TemplateResponse(
            "predict_v2.html",
            {
                "request": request,
                "players": players,
                "selected_player_a": player_a,
                "selected_player_b": player_b,
            },
        )

    finally:
        db.close()


@router.get("/value-bet")
def value_bet_analysis(
    probability: float,
    bookmaker_odds: float,
):
    value_bet = calculate_value_bet(
        probability,
        bookmaker_odds,
    )

    if not value_bet:
        return {
            "error": "Bookmaker odds must be greater than 1.00",
        }

    return {
        "probability": probability,
        "value_bet": value_bet,
    }


@router.get("/predict-v2-result")
def predict_v2_result(
    request: Request,
    player_a: str,
    player_b: str,
    bookmaker_odds: float = None,
):
    db = SessionLocal()

    try:
        players = get_players(db)

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

        result = build_prediction(
            db,
            player_a,
            player_b,
        )

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

        result["value_bet"] = None

        if bookmaker_odds is not None:
            recommended_selection = result["recommendation"]["selection"]

            selected_probability = (
                result["win_prob_a"]
                if recommended_selection == player_a
                else result["win_prob_b"]
            )

            result["value_bet"] = calculate_value_bet(
                selected_probability,
                bookmaker_odds,
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


@router.get("/predict-ui")
def predict_ui(
    request: Request,
    player_a: str,
    player_b: str,
):
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

        result = build_prediction(
            db,
            player_a,
            player_b,
        )

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