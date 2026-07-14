def build_recommendation(result):
    player_a = result["player_a"]
    player_b = result["player_b"]

    probability_a = result["win_prob_a"]
    probability_b = result["win_prob_b"]

    if probability_a >= probability_b:
        selection = player_a
        probability = probability_a
    else:
        selection = player_b
        probability = probability_b

    fair_odds = round(1 / probability, 2) if probability > 0 else 0

    if probability >= 0.70:
        confidence = "High"
        stars = 5
    elif probability >= 0.62:
        confidence = "Good"
        stars = 4
    elif probability >= 0.55:
        confidence = "Moderate"
        stars = 3
    else:
        confidence = "Low"
        stars = 2

    reasons = []

    profile_a = result["profile_a"]
    profile_b = result["profile_b"]

    if selection == player_a:
        selected_profile = profile_a
        opponent_profile = profile_b
        selected_expected_180s = result["expected_180s_a"]
        opponent_expected_180s = result["expected_180s_b"]
        simulation_probability = result["simulation"]["player_a_win"]
    else:
        selected_profile = profile_b
        opponent_profile = profile_a
        selected_expected_180s = result["expected_180s_b"]
        opponent_expected_180s = result["expected_180s_a"]
        simulation_probability = result["simulation"]["player_b_win"]

    if selected_profile["dartsedge_rating"] > opponent_profile["dartsedge_rating"]:
        reasons.append("Higher DartsEdge Rating")

    if selected_profile["elo"] > opponent_profile["elo"]:
        reasons.append("Higher Elo rating")

    if selected_expected_180s > opponent_expected_180s:
        reasons.append("Stronger expected 180 scoring")

    if simulation_probability >= 0.55:
        reasons.append(
            f"Won {round(simulation_probability * 100, 1)}% "
            "of Monte Carlo simulations"
        )

    if not reasons:
        reasons.append("Small overall model advantage")

    return {
        "market": "Match Winner",
        "selection": selection,
        "probability": round(probability * 100, 1),
        "confidence": confidence,
        "stars": stars,
        "fair_odds": fair_odds,
        "minimum_odds": round(fair_odds * 1.05, 2),
        "reasons": reasons,
    }