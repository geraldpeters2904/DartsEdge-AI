from app.models.match import Match


def get_head_to_head(db, player_a, player_b):
    matches = (
        db.query(Match)
        .filter(
            (
                ((Match.player_a == player_a) & (Match.player_b == player_b))
                |
                ((Match.player_a == player_b) & (Match.player_b == player_a))
            )
        )
        .order_by(Match.date.desc())
        .all()
    )

    wins_a = 0
    wins_b = 0

    current_streak = 0
    streak_player = None

    for match in matches:

        winner = match.winner

        if winner == player_a:
            wins_a += 1
        elif winner == player_b:
            wins_b += 1

        if streak_player is None:
            streak_player = winner
            current_streak = 1

        elif winner == streak_player:
            current_streak += 1

        else:
            break

    total_matches = len(matches)

    if total_matches == 0:
        return {
            "matches": 0,
            "wins_a": 0,
            "wins_b": 0,
            "win_pct_a": 50,
            "win_pct_b": 50,
            "streak_player": None,
            "streak": 0,
            "confidence": 50,
            "last_match": None,
        }

    win_pct_a = round((wins_a / total_matches) * 100, 1)
    win_pct_b = round((wins_b / total_matches) * 100, 1)

    confidence = 50

    confidence += abs(win_pct_a - 50) * 0.6

    confidence += min(current_streak * 4, 20)

    confidence = round(min(confidence, 95), 1)

    return {
        "matches": total_matches,
        "wins_a": wins_a,
        "wins_b": wins_b,
        "win_pct_a": win_pct_a,
        "win_pct_b": win_pct_b,
        "streak_player": streak_player,
        "streak": current_streak,
        "confidence": confidence,
        "last_match": matches[0],
    }