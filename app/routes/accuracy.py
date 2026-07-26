from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.models.prediction import Prediction
from app.services.accuracy_service import build_confidence_bands
from app.templates_config import templates


router = APIRouter()


@router.get("/accuracy")
def accuracy_page(request: Request):
    db = SessionLocal()

    try:
        predictions = db.query(Prediction).all()
        confidence_bands = build_confidence_bands(predictions)

        total_predictions = len(predictions)

        completed_predictions = len(
            [
                prediction
                for prediction in predictions
                if prediction.winner_correct is not None
            ]
        )

        winner_correct = len(
            [
                prediction
                for prediction in predictions
                if prediction.winner_correct == 1
            ]
        )

        winner_incorrect = len(
            [
                prediction
                for prediction in predictions
                if prediction.winner_correct == 0
            ]
        )

        winner_pending = total_predictions - completed_predictions

        first_180_completed = len(
            [
                prediction
                for prediction in predictions
                if prediction.first_180_correct is not None
            ]
        )

        first_180_correct = len(
            [
                prediction
                for prediction in predictions
                if prediction.first_180_correct == 1
            ]
        )

        first_180_incorrect = len(
            [
                prediction
                for prediction in predictions
                if prediction.first_180_correct == 0
            ]
        )

        first_180_pending = total_predictions - first_180_completed

        winner_accuracy = (
            round(
                (winner_correct / completed_predictions) * 100,
                1,
            )
            if completed_predictions
            else 0
        )

        first_180_accuracy = (
            round(
                (first_180_correct / first_180_completed) * 100,
                1,
            )
            if first_180_completed
            else 0
        )

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
                "confidence_bands": confidence_bands,
            },
        )

    finally:
        db.close()