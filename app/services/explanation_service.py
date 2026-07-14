def build_match_explanation(profile_a, profile_b, simulation):

    rating_diff = round(
        profile_a["dartsedge_rating"] -
        profile_b["dartsedge_rating"],
        1,
    )

    elo_diff = round(
        profile_a["elo"] -
        profile_b["elo"]
    )

    expected_a = round(profile_a["form"]["expected"], 2)
    expected_b = round(profile_b["form"]["expected"], 2)

    strengths = []
    risks = []

    if rating_diff > 0:
        strengths.append(
            f"Higher DartsEdge Rating (+{rating_diff})"
        )
    elif rating_diff < 0:
        risks.append(
            f"Opponent has higher DartsEdge Rating (+{abs(rating_diff)})"
        )

    if elo_diff > 0:
        strengths.append(
            f"Higher Elo (+{elo_diff})"
        )
    elif elo_diff < 0:
        risks.append(
            f"Opponent has higher Elo (+{abs(elo_diff)})"
        )

    if expected_a > expected_b:
        strengths.append(
            "Better recent 180 scoring"
        )
    elif expected_a < expected_b:
        risks.append(
            "Opponent scoring better recently"
        )

    verdict = (
        f"{profile_a['name']} has the stronger overall statistical profile."
        if simulation["player_a_win"] >= 0.5
        else
        f"{profile_b['name']} has the stronger overall statistical profile."
    )

    return {
        "strengths": strengths,
        "risks": risks,
        "simulation_pct": round(
            max(
                simulation["player_a_win"],
                simulation["player_b_win"]
            ) * 100,
            1,
        ),
        "expected_a": expected_a,
        "expected_b": expected_b,
        "rating_diff": abs(rating_diff),
        "verdict": verdict,
    }