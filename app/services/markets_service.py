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
    """Build deterministic Poisson-based 180 markets."""
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

    total_over_05 = probability_over(0.5, total_expected)
    total_over_15 = probability_over(1.5, total_expected)
    total_over_25 = probability_over(2.5, total_expected)
    total_over_35 = probability_over(3.5, total_expected)

    if data_available:
        most_180s_a = 0.0
        most_180s_draw = 0.0
        most_180s_b = 0.0

        # Forty 180s is far beyond any realistic MODUS match count.
        # Truncating here leaves effectively all Poisson probability mass.
        max_count = 40

        for a_count in range(max_count + 1):
            a_probability = poisson_probability(
                a_count,
                player_a_expected,
            )

            for b_count in range(max_count + 1):
                joint_probability = (
                    a_probability
                    * poisson_probability(
                        b_count,
                        player_b_expected,
                    )
                )

                if a_count > b_count:
                    most_180s_a += joint_probability
                elif a_count == b_count:
                    most_180s_draw += joint_probability
                else:
                    most_180s_b += joint_probability
    else:
        most_180s_a = 0.5
        most_180s_draw = 0.0
        most_180s_b = 0.5

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
        "total": {
            "expected": round(total_expected, 3),
            "over_0_5": round(total_over_05, 3),
            "over_1_5": round(total_over_15, 3),
            "over_2_5": round(total_over_25, 3),
            "over_3_5": round(total_over_35, 3),
        },
        "most_180s_a": round(most_180s_a, 3),
        "most_180s_draw": round(most_180s_draw, 3),
        "most_180s_b": round(most_180s_b, 3),
        "most_180s_data_available": data_available,
    }

