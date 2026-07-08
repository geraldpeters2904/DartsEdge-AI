def compare_players(profile_a, profile_b):

    reasons_a = []
    reasons_b = []

    if profile_a["elo"] > profile_b["elo"]:
        reasons_a.append("Higher Elo rating")
    elif profile_b["elo"] > profile_a["elo"]:
        reasons_b.append("Higher Elo rating")

    if profile_a["win_pct"] > profile_b["win_pct"]:
        reasons_a.append("Better win percentage")
    elif profile_b["win_pct"] > profile_a["win_pct"]:
        reasons_b.append("Better win percentage")

    if profile_a["average"] > profile_b["average"]:
        reasons_a.append("Higher scoring average")
    elif profile_b["average"] > profile_a["average"]:
        reasons_b.append("Higher scoring average")

    if profile_a["checkout"] > profile_b["checkout"]:
        reasons_a.append("Better checkout percentage")
    elif profile_b["checkout"] > profile_a["checkout"]:
        reasons_b.append("Better checkout percentage")

    if profile_a["form"]["expected"] > profile_b["form"]["expected"]:
        reasons_a.append("Stronger recent 180 form")
    elif profile_b["form"]["expected"] > profile_a["form"]["expected"]:
        reasons_b.append("Stronger recent 180 form")

    confidence = int(
        (
            profile_a["confidence"] +
            profile_b["confidence"]
        ) / 2
    )

    if len(reasons_a) > len(reasons_b):
        favoured_player = profile_a["name"]
    elif len(reasons_b) > len(reasons_a):
        favoured_player = profile_b["name"]
    else:
        favoured_player = "Too close to call"

    return {
        "favoured_player": favoured_player,
        "confidence": confidence,
        "reasons_a": reasons_a,
        "reasons_b": reasons_b,
        "reason_count_a": len(reasons_a),
        "reason_count_b": len(reasons_b)
    }