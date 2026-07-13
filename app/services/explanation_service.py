def build_match_explanation(profile_a, profile_b, simulation):
    reasons = []

    rating_diff = round(
        profile_a["dartsedge_rating"] - profile_b["dartsedge_rating"],
        1,
    )

    if rating_diff > 0:
        reasons.append(
            f"{profile_a['name']} has the higher DartsEdge Rating (+{rating_diff})"
        )
    elif rating_diff < 0:
        reasons.append(
            f"{profile_b['name']} has the higher DartsEdge Rating (+{abs(rating_diff)})"
        )
    else:
        reasons.append("Both players have the same DartsEdge Rating")

    elo_diff = round(profile_a["elo"] - profile_b["elo"])

    if elo_diff > 0:
        reasons.append(
            f"{profile_a['name']} has the higher Elo rating (+{elo_diff})"
        )
    elif elo_diff < 0:
        reasons.append(
            f"{profile_b['name']} has the higher Elo rating (+{abs(elo_diff)})"
        )
    else:
        reasons.append("Both players have the same Elo rating")

    form_diff = round(
        profile_a["form"]["expected"] - profile_b["form"]["expected"],
        2,
    )

    if form_diff > 0:
        reasons.append(
            f"{profile_a['name']} has stronger 180 form "
            f"(+{form_diff} expected 180s)"
        )
    elif form_diff < 0:
        reasons.append(
            f"{profile_b['name']} has stronger 180 form "
            f"(+{abs(form_diff)} expected 180s)"
        )
    else:
        reasons.append("Recent 180 form is level")

    simulation_a_pct = round(simulation["player_a_win"] * 100, 1)
    simulation_b_pct = round(simulation["player_b_win"] * 100, 1)

    if simulation_a_pct >= simulation_b_pct:
        reasons.append(
            f"{profile_a['name']} won {simulation_a_pct}% "
            "of Monte Carlo simulations"
        )
    else:
        reasons.append(
            f"{profile_b['name']} won {simulation_b_pct}% "
            "of Monte Carlo simulations"
        )

    return reasons