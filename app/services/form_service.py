from app.models.match_player_stats import MatchPlayerStats


def average_180s(records):
    if not records:
        return 0

    total = sum(r.one80s for r in records)
    return total / len(records)


def weighted_expected_180s(db, player_name):
    records = db.query(MatchPlayerStats).filter(
        MatchPlayerStats.player_name == player_name
    ).order_by(MatchPlayerStats.id.desc()).all()

    last_5 = records[:5]
    last_10 = records[:10]
    all_matches = records

    avg_5 = average_180s(last_5)
    avg_10 = average_180s(last_10)
    avg_all = average_180s(all_matches)

    expected = (avg_5 * 0.5) + (avg_10 * 0.3) + (avg_all * 0.2)

    return {
        "expected": round(expected, 2),
        "last_5": round(avg_5, 2),
        "last_10": round(avg_10, 2),
        "career": round(avg_all, 2)
    }