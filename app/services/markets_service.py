import math
from typing import Dict


def poisson_probability(k: int, expected: float) -> float:
    """Return the Poisson probability for exactly ``k`` events."""
    return (expected ** k) * math.exp(-expected) / math.factorial(k)


def probability_over(line: float, expected: float) -> float:
    """Return the probability of the event count finishing above ``line``."""
    cutoff = int(line)
    probability_under_or_equal = 0.0

    for k in range(0, cutoff + 1):
        probability_under_or_equal += poisson_probability(k, expected)

    return 1 - probability_under_or_equal


def one80_markets(player_a_expected: float, player_b_expected: float) -> Dict[str, object]:
    """Build 180 markets without failing when both expectations are zero.

    New players, incomplete imports and demo records may not yet have usable
    180 history. In that case the over probabilities remain zero and the
    internal most-180s split falls back to an explicitly neutral 50/50 value.
    ``most_180s_data_available`` lets templates avoid presenting that fallback
    as evidence-backed analysis.
    """
    player_a_expected = max(float(player_a_expected or 0.0), 0.0)
    player_b_expected = max(float(player_b_expected or 0.0), 0.0)

    a_over_05 = probability_over(0.5, player_a_expected)
    a_over_15 = probability_over(1.5, player_a_expected)
    a_over_25 = probability_over(2.5, player_a_expected)

    b_over_05 = probability_over(0.5, player_b_expected)
    b_over_15 = probability_over(1.5, player_b_expected)
    b_over_25 = probability_over(2.5, player_b_expected)

    total_expected = player_a_expected + player_b_expected
    data_available = total_expected > 0

    if data_available:
        most_180s_a = player_a_expected / total_expected
    else:
        most_180s_a = 0.5

    return {
        "player_a": {
            "over_0_5": round(a_over_05, 3),
            "over_1_5": round(a_over_15, 3),
            "over_2_5": round(a_over_25, 3),
        },
        "player_b": {
            "over_0_5": round(b_over_05, 3),
            "over_1_5": round(b_over_15, 3),
            "over_2_5": round(b_over_25, 3),
        },
        "most_180s_a": round(most_180s_a, 3),
        "most_180s_b": round(1 - most_180s_a, 3),
        "most_180s_data_available": data_available,
    }
