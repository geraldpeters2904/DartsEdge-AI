from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.models.prediction import Prediction
from app.templates_config import templates


router = APIRouter()


@router.get("/update-prediction-result")
def update_prediction_result_page(request: Request):
    db = SessionLocal()

    try:
        predictions = (
            db.query(Prediction)
            .order_by(Prediction.created_at.desc())
            .all()
        )

        rows = [
            {
                "id": prediction.id,
                "created_at": prediction.created_at,
                "player_a": prediction.player_a,
                "player_b": prediction.player_b,
            }
            for prediction in predictions
        ]

        return templates.TemplateResponse(
            "update_prediction.html",
            {
                "request": request,
                "predictions": rows,
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
        return {"error": "Prediction ID was not submitted"}

    if not actual_winner:
        return {
            "error": "Actual winner was not submitted",
            "submitted_form": dict(form),
        }

    db = SessionLocal()

    try:
        prediction = (
            db.query(Prediction)
            .filter(Prediction.id == int(prediction_id))
            .first()
        )

        if not prediction:
            return {"error": "Prediction not found"}

        prediction.actual_winner = actual_winner
        prediction.actual_first_180_player = actual_first_180_player

        prediction.winner_correct = (
            1
            if prediction.predicted_winner == actual_winner
            else 0
        )

        if actual_first_180_player:
            predicted_first_180 = (
                prediction.player_a
                if prediction.first_180_a >= prediction.first_180_b
                else prediction.player_b
            )

            prediction.first_180_correct = (
                1
                if predicted_first_180 == actual_first_180_player
                else 0
            )

        db.commit()

        return {
            "message": "Prediction updated",
            "prediction_id": prediction_id,
        }

    finally:
        db.close()