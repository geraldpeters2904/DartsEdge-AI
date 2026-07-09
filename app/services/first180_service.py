from app.models.match import Match


def first_180_profile(db, player_name):
    matches = db.query(Match).filter(
        (Match.player_a == player_name) | (Match.player_b == player_name)
    ).order_by(Match.date.desc()).all()

    if not matches:
        return {
            "matches": 0,
            "first_180s": 0,
            "first_180_pct": 0,
            "last_10_pct": 0
        }

    first_180s = 0
    recent_first_180s = 0
    recent_matches = matches[:10]

    for match in matches:
        if match.first_180_player == player_name:
            first_180s += 1

    for match in recent_matches:
        if match.first_180_player == player_name:
            recent_first_180s += 1

    return {
        "matches": len(matches),
        "first_180s": first_180s,
        "first_180_pct": round(first_180s / len(matches), 3),
        "last_10_pct": round(recent_first_180s / len(recent_matches), 3)
    }


def first_180_market(db, player_a, player_b):
    profile_a = first_180_profile(db, player_a)
    profile_b = first_180_profile(db, player_b)

    score_a = (profile_a["first_180_pct"] * 0.6) + (profile_a["last_10_pct"] * 0.4)
    score_b = (profile_b["first_180_pct"] * 0.6) + (profile_b["last_10_pct"] * 0.4)

    total = score_a + score_b

    if total == 0:
        return {
            "player_a": 0.5,
            "player_b": 0.5,
            "profile_a": profile_a,
            "profile_b": profile_b
        }

    return {
        "player_a": round(score_a / total, 3),
        "player_b": round(score_b / total, 3),
        "profile_a": profile_a,
        "profile_b": profile_b
    }