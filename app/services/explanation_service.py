def build_match_explanation(
    profile_a,
    profile_b,
    simulation,
    head_to_head=None,
):
    player_a = profile_a["name"]
    player_b = profile_b["name"]

    rating_diff = round(
        profile_a["dartsedge_rating"]
        - profile_b["dartsedge_rating"],
        1,
    )

    elo_diff = round(
        profile_a["elo"]
        - profile_b["elo"]
    )

    expected_a = round(
        profile_a["form"]["expected"],
        2,
    )

    expected_b = round(
        profile_b["form"]["expected"],
        2,
    )

    simulation_a = simulation["player_a_win"]
    simulation_b = simulation["player_b_win"]

    favoured_player = (
        player_a
        if simulation_a >= simulation_b
        else player_b
    )

    simulation_pct = round(
        max(simulation_a, simulation_b) * 100,
        1,
    )

    strengths = []
    risks = []

    if favoured_player == player_a:
        if rating_diff > 0:
            strengths.append(
                f"{player_a} has the higher DartsEdge Rating."
            )
        else:
            risks.append(
                f"{player_b} has the higher DartsEdge Rating."
            )

        if elo_diff > 0:
            strengths.append(
                f"{player_a} has performed better against comparable opposition."
            )
        else:
            risks.append(
                f"{player_b} has the stronger Elo profile."
            )

        if expected_a > expected_b:
            strengths.append(
                f"{player_a} has shown stronger recent 180 scoring."
            )
        elif expected_a < expected_b:
            risks.append(
                f"{player_b} has been scoring 180s more consistently recently."
            )

    else:
        if rating_diff < 0:
            strengths.append(
                f"{player_b} has the higher DartsEdge Rating."
            )
        else:
            risks.append(
                f"{player_a} has the higher DartsEdge Rating."
            )

        if elo_diff < 0:
            strengths.append(
                f"{player_b} has performed better against comparable opposition."
            )
        else:
            risks.append(
                f"{player_a} has the stronger Elo profile."
            )

        if expected_b > expected_a:
            strengths.append(
                f"{player_b} has shown stronger recent 180 scoring."
            )
        elif expected_b < expected_a:
            risks.append(
                f"{player_a} has been scoring 180s more consistently recently."
            )

    if head_to_head and head_to_head["matches"] >= 3:
        h2h_leader = None

        if head_to_head["wins_a"] > head_to_head["wins_b"]:
            h2h_leader = player_a
        elif head_to_head["wins_b"] > head_to_head["wins_a"]:
            h2h_leader = player_b

        if h2h_leader == favoured_player:
            strengths.append(
                f"{favoured_player} holds the stronger head-to-head record."
            )
        elif h2h_leader:
            risks.append(
                f"{h2h_leader} holds the stronger head-to-head record."
            )

    if simulation_pct >= 75:
        confidence = "High"
    elif simulation_pct >= 60:
        confidence = "Moderate"
    else:
        confidence = "Low"

    headline = (
        f"{favoured_player} is the preferred selection."
    )

    summary = (
        f"The model gives {favoured_player} a {simulation_pct}% chance "
        f"of winning based on the available performance data. "
        f"The overall evidence favours {favoured_player}, although "
        f"the match may still be competitive."
    )

    if confidence == "High":
        summary = (
            f"{favoured_player} is favoured across several important "
            f"indicators, and the simulation shows strong agreement "
            f"with that view."
        )
    elif confidence == "Low":
        summary = (
            f"{favoured_player} has a slight overall edge, but the "
            f"players are closely matched and the prediction should "
            f"be treated cautiously."
        )

    return {
        "headline": headline,
        "summary": summary,
        "confidence": confidence,
        "strengths": strengths,
        "risks": risks,
        "favoured_player": favoured_player,
        "simulation_pct": simulation_pct,
        "expected_a": expected_a,
        "expected_b": expected_b,
    }