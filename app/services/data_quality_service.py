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

    # Preserve the original per-match missing-player semantics
    # while avoiding two database lookups for every scheduled match.
    player_names = {
        name for (name,) in db.query(Player.name).all()
    }

    scheduled_matches = (
        db.query(Match.player_a, Match.player_b)
        .filter(Match.status == "scheduled")
        .all()
    )

    missing_players = sum(
        1
        for player_a, player_b in scheduled_matches
        if player_a not in player_names or player_b not in player_names
    )

    # Count completed matches with fewer than two stats rows
    # in the database rather than issuing one query per match.
    stats_counts = (
        db.query(
            MatchPlayerStats.match_id,
            func.count(MatchPlayerStats.id).label("stats_count"),
        )
        .group_by(MatchPlayerStats.match_id)
        .subquery()
    )

    missing_match_stats = (
        db.query(Match.id)
        .outerjoin(
            stats_counts,
            Match.id == stats_counts.c.match_id,
        )
        .filter(
            Match.status == "completed",
            func.coalesce(stats_counts.c.stats_count, 0) < 2,
        )
        .count()
    )
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