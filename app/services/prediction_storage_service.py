from app.models.prediction import Prediction


def save_prediction(db, result):
    """
    Save a generated prediction to the database.
    """

    recommendation = result["recommendation"]
    first_180 = result.get("first_180", {})

    prediction = Prediction(
        player_a=result["player_a"],
        player_b=result["player_b"],
        predicted_winner=recommendation["selection"],
        win_prob_a=result["win_prob_a"],
        win_prob_b=result["win_prob_b"],
        confidence=int(round(recommendation["probability"])),
        rating_a=result["profile_a"]["elo"],
        rating_b=result["profile_b"]["elo"],
        first_180_a=first_180.get("player_a"),
        first_180_b=first_180.get("player_b"),
    )

    db.add(prediction)
    db.commit()
    db.refresh(prediction)

    return prediction