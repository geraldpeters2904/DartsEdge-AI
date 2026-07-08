from app.models.player import Player
from app.models.player_stats import PlayerStats
from app.services.form_service import weighted_expected_180s


def get_player_profile(db, player_name):

    player = db.query(Player).filter(
        Player.name == player_name
    ).first()

    if not player:
        return None

    stats = db.query(PlayerStats).filter(
        PlayerStats.player_id == player.id
    ).first()

    form = weighted_expected_180s(db, player_name)

    matches = stats.matches if stats else 0
    wins = stats.wins if stats else 0
    losses = stats.losses if stats else 0

    confidence = min(95, 40 + matches)

    return {
        "name": player.name,
        "elo": player.elo,
        "average": player.average,
        "checkout": player.checkout,
        "matches": matches,
        "wins": wins,
        "losses": losses,
        "win_pct": round((wins / matches) * 100, 1) if matches else 0,
        "legs_won": stats.legs_won if stats else 0,
        "legs_lost": stats.legs_lost if stats else 0,
        "form": form,
        "confidence": confidence
    }