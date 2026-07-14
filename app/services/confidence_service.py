def build_confidence_breakdown(
    profile_a,
    profile_b,
    simulation,
    probability,
    head_to_head=None,
):
    elo_gap = abs(
        profile_a["elo"] - profile_b["elo"]
    )

    rating_gap = abs(
        profile_a["dartsedge_rating"]
        - profile_b["dartsedge_rating"]
    )

    form_gap = abs(
        profile_a["form"]["expected"]
        - profile_b["form"]["expected"]
    )

    simulation_score = round(
        max(
            simulation["player_a_win"],
            simulation["player_b_win"],
        ) * 100
    )

    elo_score = min(
        100,
        round(elo_gap / 2),
    )

    rating_score = min(
        100,
        round(rating_gap * 10),
    )

    form_score = min(
        100,
        round(form_gap * 100),
    )

    overall = round(probability * 100)

    h2h_score = (
        head_to_head["confidence"]
        if head_to_head
        else 50
    )

    if overall >= 75:
        summary = (
            "Strong agreement between all major prediction models."
        )
    elif overall >= 65:
        summary = (
            "Most prediction models agree with moderate confidence."
        )
    else:
        summary = (
            "Prediction is competitive. Consider additional markets."
        )

    return {
        "overall": overall,
        "elo": elo_score,
        "rating": rating_score,
        "form": form_score,
        "simulation": simulation_score,
        "head_to_head": h2h_score,
        "summary": summary,
    }