from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app.services.prediction_storage_service import save_prediction
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
    request: Request,
    probability: float,
    bookmaker_odds: float,
):
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

    decimal_probability = probability / 100

    value_bet = calculate_value_bet(
        decimal_probability,
        bookmaker_odds,
    )

    if not value_bet:
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

    return templates.TemplateResponse(
        "value_bets.html",
        {
            "request": request,
            "probability": probability,
            "bookmaker_odds": bookmaker_odds,
            "value_bet": value_bet,
        },
    )


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

        saved_prediction = save_prediction(db, result)

        result["prediction_id"] = saved_prediction.id

        for opportunity in result["trading_opportunities"]:
            opportunity["prediction_id"] = saved_prediction.id

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



@router.post("/save-prediction")
async def save_prediction_route(
    request: Request,
):
    form = await request.form()

    player_a = form.get("player_a")
    player_b = form.get("player_b")

    if not player_a or not player_b:
        return {"error": "Player names not supplied."}

    db = SessionLocal()

    try:
        result = build_prediction(
            db,
            player_a,
            player_b,
        )

        if not result:
            return {"error": "Prediction could not be generated."}

        save_prediction(db, result)

        return RedirectResponse(
            url="/prediction-history",
            status_code=303,
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


@router.get("/value-bet-page")
def value_bet_page(
    request: Request,
    probability: float = None,
    selection: str = None,
    opponent: str = None,
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