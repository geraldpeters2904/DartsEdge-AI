from app.models.match import Match
from app.models.player import Player
from app.models.prediction import Prediction
from app.services.player_profile_service import get_player_profile


def build_dashboard_data(db):
    player_count = db.query(Player).count()
    match_count = db.query(Match).count()
    prediction_count = db.query(Prediction).count()

    completed_predictions = (
        db.query(Prediction)
        .filter(Prediction.winner_correct.isnot(None))
        .all()
    )

    correct_predictions = len([
        prediction
        for prediction in completed_predictions
        if prediction.winner_correct == 1
    ])

    winner_accuracy = (
        round(
            (correct_predictions / len(completed_predictions)) * 100,
            1,
        )
        if completed_predictions
        else 0
    )

    players = db.query(Player).all()

    profiles = []

    for player in players:
        profile = get_player_profile(db, player.name)

        if profile:
            profiles.append(profile)

    profiles.sort(
        key=lambda profile: profile["dartsedge_rating"],
        reverse=True,
    )

    top_players = profiles[:5]

    recent_matches = [
        {
            "date": match.date,
            "player_a": match.player_a,
            "player_b": match.player_b,
            "winner": match.winner,
            "score": match.score,
        }
        for match in (
            db.query(Match)
            .order_by(Match.date.desc())
            .limit(5)
            .all()
        )
    ]

    return {
        "player_count": player_count,
        "match_count": match_count,
        "prediction_count": prediction_count,
        "winner_accuracy": winner_accuracy,
        "top_players": top_players,
        "recent_matches": recent_matches,
    }