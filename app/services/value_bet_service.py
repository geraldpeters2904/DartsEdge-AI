def calculate_value_bet(
    probability,
    bookmaker_odds,
):
    if bookmaker_odds <= 1:
        return None

    fair_odds = round(1 / probability, 2)

    implied_probability = 1 / bookmaker_odds

    edge = (
        probability - implied_probability
    ) * 100

    expected_value = (
        probability * bookmaker_odds
    ) - 1

    if edge >= 10:
        recommendation = "VALUE BET"
        stars = 5

    elif edge >= 5:
        recommendation = "SMALL VALUE"
        stars = 4

    elif edge >= 0:
        recommendation = "FAIR PRICE"
        stars = 3

    else:
        recommendation = "NO VALUE"
        stars = 1

    return {
        "fair_odds": fair_odds,
        "bookmaker_odds": bookmaker_odds,
        "edge": round(edge, 1),
        "expected_value": round(expected_value * 100, 1),
        "recommendation": recommendation,
        "stars": stars,
    }