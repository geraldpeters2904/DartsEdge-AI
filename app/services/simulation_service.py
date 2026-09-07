import math
from collections import Counter


def _elo_probability(profile_a, profile_b):
    elo_a = profile_a["elo"]
    elo_b = profile_b["elo"]

    if elo_a == elo_b:
        return 0.5

    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))


def _score_probability(leg_win_prob_a, target_legs, loser_legs, player_a_wins):
    total_before_final_leg = (target_legs - 1) + loser_legs
    arrangements = math.comb(
        total_before_final_leg,
        loser_legs,
    )

    if player_a_wins:
        return (
            arrangements
            * (leg_win_prob_a ** target_legs)
            * ((1 - leg_win_prob_a) ** loser_legs)
        )

    return (
        arrangements
        * ((1 - leg_win_prob_a) ** target_legs)
        * (leg_win_prob_a ** loser_legs)
    )


def simulate_match(
    profile_a,
    profile_b,
    simulations=10000,
    leg_win_prob_a=None,
    best_of=7,
):
    """
    Return exact match-market probabilities.

    ``simulations`` is retained for backward compatibility but is no longer
    used. The calculation is deterministic.

    ``best_of`` must be a positive odd number. For example, Best of 7 means
    first to 4 legs.
    """
    del simulations

    if best_of <= 0 or best_of % 2 == 0:
        raise ValueError("best_of must be a positive odd number")

    if leg_win_prob_a is None:
        leg_win_prob_a = _elo_probability(
            profile_a,
            profile_b,
        )

    leg_win_prob_a = float(leg_win_prob_a)

    if not 0.0 <= leg_win_prob_a <= 1.0:
        raise ValueError(
            "leg_win_prob_a must be between 0 and 1"
        )

    target_legs = (best_of // 2) + 1

    scores = Counter()

    for loser_legs in range(target_legs):
        score_a_win = f"{target_legs}-{loser_legs}"
        score_b_win = f"{loser_legs}-{target_legs}"

        scores[score_a_win] = _score_probability(
            leg_win_prob_a,
            target_legs,
            loser_legs,
            player_a_wins=True,
        )

        scores[score_b_win] = _score_probability(
            leg_win_prob_a,
            target_legs,
            loser_legs,
            player_a_wins=False,
        )

    player_a_win = sum(
        probability
        for score, probability in scores.items()
        if int(score.split("-")[0]) == target_legs
    )
    player_b_win = 1 - player_a_win

    player_a_minus_1_5 = 0.0
    player_a_minus_2_5 = 0.0
    player_b_plus_2_5 = 0.0
    over_5_5 = 0.0
    over_6_5 = 0.0

    for score, probability in scores.items():
        legs_a, legs_b = (
            int(value)
            for value in score.split("-")
        )

        margin_a = legs_a - legs_b
        total = legs_a + legs_b

        if margin_a > 1.5:
            player_a_minus_1_5 += probability

        if margin_a > 2.5:
            player_a_minus_2_5 += probability

        if margin_a < 2.5:
            player_b_plus_2_5 += probability

        if total > 5.5:
            over_5_5 += probability

        if total > 6.5:
            over_6_5 += probability

    return {
        "player_a_win": round(player_a_win, 3),
        "player_b_win": round(player_b_win, 3),
        "scores": {
            score: round(probability, 3)
            for score, probability in scores.items()
        },
        "handicaps": {
            "player_a_minus_1_5": round(
                player_a_minus_1_5,
                3,
            ),
            "player_a_minus_2_5": round(
                player_a_minus_2_5,
                3,
            ),
            "player_b_plus_2_5": round(
                player_b_plus_2_5,
                3,
            ),
        },
        "total_legs": {
            "over_5_5": round(over_5_5, 3),
            "over_6_5": round(over_6_5, 3),
        },
    }
