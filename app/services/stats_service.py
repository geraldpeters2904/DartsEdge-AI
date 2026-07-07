from app.models.player_stats import PlayerStats


def get_or_create_stats(db, player):
    stats = db.query(PlayerStats).filter(PlayerStats.player_id == player.id).first()

    if not stats:
        stats = PlayerStats(player_id=player.id)
        db.add(stats)
        db.flush()

    return stats


def parse_score(score):
    left, right = score.split("-")
    return int(left), int(right)


def update_player_stats(db, player_a, player_b, winner, score):
    stats_a = get_or_create_stats(db, player_a)
    stats_b = get_or_create_stats(db, player_b)

    legs_a, legs_b = parse_score(score)

    stats_a.matches += 1
    stats_b.matches += 1

    stats_a.legs_won += legs_a
    stats_a.legs_lost += legs_b

    stats_b.legs_won += legs_b
    stats_b.legs_lost += legs_a

    if winner == player_a.name:
        stats_a.wins += 1
        stats_b.losses += 1
    elif winner == player_b.name:
        stats_b.wins += 1
        stats_a.losses += 1