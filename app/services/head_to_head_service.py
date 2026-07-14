from app.models.match import Match


def get_head_to_head(
    db,
    player_a,
    player_b,
):
    matches = (
        db.query(Match)
        .filter(
            (
                (Match.player_a == player_a)
                & (Match.player_b == player_b)
            )
            |
            (
                (Match.player_a == player_b)
                & (Match.player_b == player_a)
            )
        )
        .order_by(Match.date.desc())
        .all()
    )

    wins_a = 0
    wins_b = 0

    for match in matches:

        if match.winner == player_a:
            wins_a += 1

        elif match.winner == player_b:
            wins_b += 1

    return {
        "matches": len(matches),
        "wins_a": wins_a,
        "wins_b": wins_b,
        "last_match": matches[0] if matches else None,
    }