import math

def win_probability(elo_a, elo_b):
    return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))


def expected_180s(player):
    base = player["one80_rate"]
    scoring_factor = player["avg"] / 85
    return base * 5 * scoring_factor


def leg_win_probability(player_a, player_b):
    score_a = player_a["avg"] * 0.7 + player_a["checkout"] * 0.3
    score_b = player_b["avg"] * 0.7 + player_b["checkout"] * 0.3
    return 1 / (1 + math.exp((score_b - score_a) / 8))


def value_edge(model_prob, market_prob=0.5):
    edge = model_prob - market_prob
    return {
        "edge": round(edge, 3),
        "value": "YES" if edge > 0.03 else "NO"
    }