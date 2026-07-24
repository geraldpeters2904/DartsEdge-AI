def calculate_value_bet(
    probability,
    bookmaker_odds,
    minimum_edge=5.0,
    minimum_confidence=60.0,
):
    if probability <= 0 or probability > 1:
        return None

    if bookmaker_odds <= 1:
        return None

    fair_odds = round(1 / probability, 2)
    implied_probability = 1 / bookmaker_odds

    edge = round(
        (probability - implied_probability) * 100,
        1,
    )

    expected_value = round(
        ((probability * bookmaker_odds) - 1) * 100,
        1,
    )

    confidence = probability * 100

    if confidence < minimum_confidence:
        recommendation = "LOW CONFIDENCE"
        stars = 1

    elif edge >= (minimum_edge * 2):
        recommendation = "VALUE BET"
        stars = 5

    elif edge >= minimum_edge:
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
        "implied_probability": round(
            implied_probability * 100,
            1,
        ),
        "edge": edge,
        "expected_value": expected_value,
        "recommendation": recommendation,
        "stars": stars,
    }