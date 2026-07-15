def build_prediction_factors(
    profile_a,
    profile_b,
    head_to_head,
):
    factors = []

    # Elo
    elo_gap = profile_a["elo"] - profile_b["elo"]

    if abs(elo_gap) > 20:
        factors.append({
            "factor": "Elo Rating",
            "winner": (
                profile_a["name"]
                if elo_gap > 0
                else profile_b["name"]
            ),
            "strength": abs(elo_gap),
            "impact": "High",
        })

    # DartsEdge Rating
    rating_gap = (
        profile_a["dartsedge_rating"]
        - profile_b["dartsedge_rating"]
    )

    if abs(rating_gap) > 1:
        factors.append({
            "factor": "DartsEdge Rating",
            "winner": (
                profile_a["name"]
                if rating_gap > 0
                else profile_b["name"]
            ),
            "strength": round(abs(rating_gap), 1),
            "impact": "Medium",
        })

    # Form
    form_gap = (
        profile_a["form"]["expected"]
        - profile_b["form"]["expected"]
    )

    if abs(form_gap) > 0.1:
        factors.append({
            "factor": "Recent 180 Form",
            "winner": (
                profile_a["name"]
                if form_gap > 0
                else profile_b["name"]
            ),
            "strength": round(abs(form_gap), 2),
            "impact": "Medium",
        })

    # Head-to-head
    if head_to_head["matches"] >= 3:
        factors.append({
            "factor": "Head-to-Head",
            "winner": (
                profile_a["name"]
                if head_to_head["wins_a"] >
                   head_to_head["wins_b"]
                else profile_b["name"]
            ),
            "strength": head_to_head["confidence"],
            "impact": "High",
        })

    return factors