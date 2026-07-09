from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates

from app.db import SessionLocal
from app.models.prediction import Prediction


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/update-prediction-result")
def update_prediction_result_page(request: Request):
    db = SessionLocal()

    predictions = (
        db.query(Prediction)
        .order_by(Prediction.created_at.desc())
        .all()
    )

    rows = []

    for p in predictions:
        rows.append({
            "id": p.id,
            "created_at": p.created_at,
            "player_a": p.player_a,
            "player_b": p.player_b
        })

    db.close()

    return templates.TemplateResponse(
        "update_prediction.html",
        {
            "request": request,
            "predictions": rows
        }
    )


@router.post("/update-prediction-result")
async def update_prediction_result(request: Request):
    form = await request.form()

    prediction_id = form.get("prediction_id")
    actual_winner = form.get("actual_winner")
    actual_first_180_player = form.get("actual_first_180_player", "")

    if not actual_winner:
        return {
            "error": "Actual winner was not submitted",
            "submitted_form": dict(form)
        }

    db = SessionLocal()

    prediction = db.query(Prediction).filter(
        Prediction.id == int(prediction_id)
    ).first()

    if not prediction:
        db.close()
        return {"error": "Prediction not found"}

    prediction.actual_winner = actual_winner
    prediction.actual_first_180_player = actual_first_180_player

    prediction.winner_correct = (
        1 if prediction.predicted_winner == actual_winner else 0
    )

    if actual_first_180_player:
        predicted_first_180 = (
            prediction.player_a
            if prediction.first_180_a >= prediction.first_180_b
            else prediction.player_b
        )

        prediction.first_180_correct = (
            1 if predicted_first_180 == actual_first_180_player else 0
        )

    db.commit()
    db.close()

    return {
        "message": "Prediction updated",
        "prediction_id": prediction_id
    }