def calculate_edge(fair_odds: float, bookmaker_odds: float) -> float:
    """
    Positive = value
    Negative = poor value
    """

    if bookmaker_odds <= 0:
        return 0.0

    return round(((bookmaker_odds / fair_odds) - 1) * 100, 1)


def value_status(edge: float) -> str:
    """
    Classify the value opportunity.
    """

    if edge >= 5:
        return "VALUE"

    if edge >= 0:
        return "FAIR"

    return "PASS"


def value_colour(edge: float) -> str:
    """
    CSS helper.
    """

    if edge >= 5:
        return "success"

    if edge >= 0:
        return "warning"

    return "danger"