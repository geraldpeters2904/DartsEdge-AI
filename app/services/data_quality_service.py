from sqlalchemy import func

from app.models.player import Player
from app.models.match import Match
from app.models.player_stats import PlayerStats
from app.models.prediction import Prediction
from app.models.match_player_stats import MatchPlayerStats


def get_data_quality(db):

    players = db.query(Player).count()

    scheduled = (
        db.query(Match)
        .filter(Match.status == "scheduled")
        .count()
    )

    completed = (
        db.query(Match)
        .filter(Match.status == "completed")
        .count()
    )

    predictions = db.query(Prediction).count()

    player_stats = db.query(PlayerStats).count()

    match_stats = db.query(MatchPlayerStats).count()

    duplicate_players = (
        db.query(Player.name)
        .group_by(Player.name)
        .having(func.count(Player.id) > 1)
        .count()
    )

    duplicate_fixtures = (
        db.query(
            Match.date,
            Match.player_a,
            Match.player_b,
        )
        .group_by(
            Match.date,
            Match.player_a,
            Match.player_b,
        )
        .having(func.count(Match.id) > 1)
        .count()
    )

    missing_players = 0

    scheduled_matches = (
        db.query(Match)
        .filter(Match.status == "scheduled")
        .all()
    )

    for match in scheduled_matches:

        a = (
            db.query(Player)
            .filter(Player.name == match.player_a)
            .first()
        )

        b = (
            db.query(Player)
            .filter(Player.name == match.player_b)
            .first()
        )

        if a is None or b is None:
            missing_players += 1

    completed_matches = (
        db.query(Match)
        .filter(Match.status == "completed")
        .all()
    )

    missing_match_stats = 0

    for match in completed_matches:

        count = (
            db.query(MatchPlayerStats)
            .filter(
                MatchPlayerStats.match_id == match.id
            )
            .count()
        )

        if count < 2:
            missing_match_stats += 1
    health_score = 100

    health_score -= duplicate_players * 10
    health_score -= duplicate_fixtures * 5
    health_score -= missing_players * 10
    health_score -= missing_match_stats * 2

    if health_score < 0:
        health_score = 0
    return {
        "players": players,
        "scheduled": scheduled,
        "completed": completed,
        "predictions": predictions,
        "player_stats": player_stats,
        "match_stats": match_stats,
        "duplicate_players": duplicate_players,
        "duplicate_fixtures": duplicate_fixtures,
        "missing_players": missing_players,
        "missing_match_stats": missing_match_stats,
        "health_score": health_score,
    }