from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.db import SessionLocal
from app.models.prediction import Prediction

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/accuracy")
def accuracy_page(request: Request):

    db = SessionLocal()

    predictions = db.query(Prediction).all()

    total_predictions = len(predictions)

    completed_predictions = len(
        [p for p in predictions if p.winner_correct is not None]
    )

    winner_correct = len(
        [p for p in predictions if p.winner_correct == 1]
    )

    winner_incorrect = len(
        [p for p in predictions if p.winner_correct == 0]
    )

    winner_pending = total_predictions - completed_predictions

    first_180_completed = len(
        [p for p in predictions if p.first_180_correct is not None]
    )

    first_180_correct = len(
        [p for p in predictions if p.first_180_correct == 1]
    )

    first_180_incorrect = len(
        [p for p in predictions if p.first_180_correct == 0]
    )

    first_180_pending = total_predictions - first_180_completed

    winner_accuracy = (
        round((winner_correct / completed_predictions) * 100, 1)
        if completed_predictions
        else 0
    )

    first_180_accuracy = (
        round((first_180_correct / first_180_completed) * 100, 1)
        if first_180_completed
        else 0
    )

    db.close()

    return templates.TemplateResponse(
        "accuracy.html",
        {
            "request": request,
            "total_predictions": total_predictions,
            "completed_predictions": completed_predictions,
            "winner_accuracy": winner_accuracy,
            "first_180_accuracy": first_180_accuracy,
            "winner_correct": winner_correct,
            "winner_incorrect": winner_incorrect,
            "winner_pending": winner_pending,
            "first_180_correct": first_180_correct,
            "first_180_incorrect": first_180_incorrect,
            "first_180_pending": first_180_pending,
        },
    )