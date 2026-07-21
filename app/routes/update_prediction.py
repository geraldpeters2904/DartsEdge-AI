from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.db import SessionLocal
from app.models.prediction import Prediction
from app.templates_config import templates


router = APIRouter()


@router.get("/update-prediction-result")
def update_prediction_result_page(
    request: Request,
    saved: int = 0,
    error: str = None,
):
    db = SessionLocal()

    try:
        predictions = (
            db.query(Prediction)
            .filter(Prediction.actual_winner.is_(None))
            .order_by(Prediction.created_at.desc())
            .all()
        )

        rows = [
            {
                "id": prediction.id,
                "created_at": prediction.created_at,
                "player_a": prediction.player_a,
                "player_b": prediction.player_b,
                "predicted_winner": prediction.predicted_winner,
                "confidence": prediction.confidence,
            }
            for prediction in predictions
        ]

        return templates.TemplateResponse(
            "update_prediction.html",
            {
                "request": request,
                "predictions": rows,
                "saved": saved == 1,
                "error": error,
            },
        )

    finally:
        db.close()


@router.post("/update-prediction-result")
async def update_prediction_result(request: Request):
    form = await request.form()

    prediction_id = form.get("prediction_id")
    actual_winner = form.get("actual_winner")
    actual_first_180_player = form.get(
        "actual_first_180_player",
        "",
    )

    if not prediction_id:
        return RedirectResponse(
            url=(
                "/update-prediction-result"
                "?error=Prediction+ID+was+not+submitted"
            ),
            status_code=303,
        )

    db = SessionLocal()

    try:
        prediction = (
            db.query(Prediction)
            .filter(Prediction.id == int(prediction_id))
            .first()
        )

        if not prediction:
            return RedirectResponse(
                url=(
                    "/update-prediction-result"
                    "?error=Prediction+was+not+found"
                ),
                status_code=303,
            )

        valid_players = {
            prediction.player_a,
            prediction.player_b,
        }

        if actual_winner not in valid_players:
            return RedirectResponse(
                url=(
                    "/update-prediction-result"
                    "?error=Please+select+a+valid+winner"
                ),
                status_code=303,
            )

        if (
            actual_first_180_player
            and actual_first_180_player not in valid_players
        ):
            return RedirectResponse(
                url=(
                    "/update-prediction-result"
                    "?error=Please+select+a+valid+first+180+player"
                ),
                status_code=303,
            )

        prediction.actual_winner = actual_winner
        prediction.actual_first_180_player = (
            actual_first_180_player or None
        )

        prediction.winner_correct = int(
            prediction.predicted_winner == actual_winner
        )

        prediction.first_180_correct = None

        if actual_first_180_player:
            if (
                prediction.first_180_a is not None
                and prediction.first_180_b is not None
            ):
                predicted_first_180 = (
                    prediction.player_a
                    if prediction.first_180_a
                    >= prediction.first_180_b
                    else prediction.player_b
                )

                prediction.first_180_correct = int(
                    predicted_first_180
                    == actual_first_180_player
                )

        db.commit()

        return RedirectResponse(
            url="/update-prediction-result?saved=1",
            status_code=303,
        )

    finally:
        db.close()