from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.db import SessionLocal
from app.models.prediction import Prediction


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/prediction-history")
def prediction_history_page(request: Request):
    db = SessionLocal()

    try:
        predictions = (
            db.query(Prediction)
            .order_by(Prediction.created_at.desc())
            .all()
        )

        rows = [
            {
                "created_at": prediction.created_at,
                "player_a": prediction.player_a,
                "player_b": prediction.player_b,
                "predicted_winner": prediction.predicted_winner,
                "win_prob_a": prediction.win_prob_a,
                "win_prob_b": prediction.win_prob_b,
                "confidence": prediction.confidence,
                "rating_a": prediction.rating_a,
                "rating_b": prediction.rating_b,
                "first_180_a": prediction.first_180_a,
                "first_180_b": prediction.first_180_b,
                "actual_winner": prediction.actual_winner,
                "winner_correct": prediction.winner_correct,
            }
            for prediction in predictions
        ]

        return templates.TemplateResponse(
            "prediction_history.html",
            {
                "request": request,
                "predictions": rows,
            },
        )

    finally:
        db.close()