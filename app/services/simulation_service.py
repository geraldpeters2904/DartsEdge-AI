import random
from collections import Counter


def simulate_match(profile_a, profile_b, simulations=10000):
    results = Counter()
    scores = Counter()
    handicaps = Counter()
    total_legs = Counter()

    win_prob_a = 0.5

    if profile_a["elo"] != profile_b["elo"]:
        win_prob_a = 1 / (1 + 10 ** ((profile_b["elo"] - profile_a["elo"]) / 400))

    for _ in range(simulations):
        legs_a = 0
        legs_b = 0

        while legs_a < 4 and legs_b < 4:
            if random.random() < win_prob_a:
                legs_a += 1
            else:
                legs_b += 1

        total = legs_a + legs_b
        margin_a = legs_a - legs_b

        if legs_a > legs_b:
            results["player_a_win"] += 1
        else:
            results["player_b_win"] += 1

        scores[f"{legs_a}-{legs_b}"] += 1

        if margin_a > 1.5:
            handicaps["player_a_minus_1_5"] += 1

        if margin_a > 2.5:
            handicaps["player_a_minus_2_5"] += 1

        if margin_a < 2.5:
            handicaps["player_b_plus_2_5"] += 1

        if total > 5.5:
            total_legs["over_5_5"] += 1

        if total > 6.5:
            total_legs["over_6_5"] += 1

    return {
        "player_a_win": round(results["player_a_win"] / simulations, 3),
        "player_b_win": round(results["player_b_win"] / simulations, 3),
        "scores": {
            score: round(count / simulations, 3)
            for score, count in scores.items()
        },
        "handicaps": {
            key: round(value / simulations, 3)
            for key, value in handicaps.items()
        },
        "total_legs": {
            key: round(value / simulations, 3)
            for key, value in total_legs.items()
        }
    }