def build_confidence_breakdown(
    profile_a,
    profile_b,
    simulation,
    final_probability,
):
    elo_gap = abs(profile_a["elo"] - profile_b["elo"])
    rating_gap = abs(
        profile_a["dartsedge_rating"] -
        profile_b["dartsedge_rating"]
    )

    form_gap = abs(
        profile_a["form"]["expected"] -
        profile_b["form"]["expected"]
    )

    simulation_strength = max(
        simulation["player_a_win"],
        simulation["player_b_win"]
    )

    # Convert raw values into simple 0–100 scores.
    elo_score = min(100, round(elo_gap / 2))
    rating_score = min(100, round(rating_gap * 10))
    form_score = min(100, round(form_gap * 100))
    simulation_score = round(simulation_strength * 100)

    overall = round(final_probability * 100)

    return {
        "elo": elo_score,
        "rating": rating_score,
        "form": form_score,
        "simulation": simulation_score,
        "overall": overall,
    }