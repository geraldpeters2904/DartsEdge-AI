from app.models.match import Match
from app.services.prediction_pipeline import build_prediction


def build_best_bets(db, limit=5):
    scheduled_matches = (
        db.query(Match)
        .filter(Match.status == "scheduled")
        .order_by(Match.date.asc())
        .all()
    )

    best_bets = []

    for match in scheduled_matches:
        prediction = build_prediction(
            db,
            match.player_a,
            match.player_b,
        )

        if not prediction:
            continue

        recommendation = prediction["recommendation"]

        best_bets.append({
            "match_id": match.id,
            "date": match.date,
            "tournament": match.tournament,
            "player_a": match.player_a,
            "player_b": match.player_b,
            "selection": recommendation["selection"],
            "probability": recommendation["probability"],
            "confidence": recommendation["confidence"],
            "stars": recommendation["stars"],
            "fair_odds": recommendation["fair_odds"],
            "minimum_odds": recommendation["minimum_odds"],
        })

    best_bets.sort(
        key=lambda bet: (
            bet["stars"],
            bet["probability"],
        ),
        reverse=True,
    )

    return best_bets[:limit]