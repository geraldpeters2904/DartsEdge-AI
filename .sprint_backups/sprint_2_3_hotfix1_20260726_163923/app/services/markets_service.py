import math


def poisson_probability(k, expected):
    return (expected ** k) * math.exp(-expected) / math.factorial(k)


def probability_over(line, expected):
    cutoff = int(line)

    probability_under_or_equal = 0

    for k in range(0, cutoff + 1):
        probability_under_or_equal += poisson_probability(k, expected)

    return 1 - probability_under_or_equal


def one80_markets(player_a_expected, player_b_expected):

    a_over_05 = probability_over(0.5, player_a_expected)
    a_over_15 = probability_over(1.5, player_a_expected)
    a_over_25 = probability_over(2.5, player_a_expected)

    b_over_05 = probability_over(0.5, player_b_expected)
    b_over_15 = probability_over(1.5, player_b_expected)
    b_over_25 = probability_over(2.5, player_b_expected)

    most_180s_a = player_a_expected / (player_a_expected + player_b_expected)

    return {
        "player_a": {
            "over_0_5": round(a_over_05, 3),
            "over_1_5": round(a_over_15, 3),
            "over_2_5": round(a_over_25, 3)
        },
        "player_b": {
            "over_0_5": round(b_over_05, 3),
            "over_1_5": round(b_over_15, 3),
            "over_2_5": round(b_over_25, 3)
        },
        "most_180s_a": round(most_180s_a, 3),
        "most_180s_b": round(1 - most_180s_a, 3)
    }