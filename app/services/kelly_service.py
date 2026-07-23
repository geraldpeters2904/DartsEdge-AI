def calculate_kelly_stake(
    probability,
    bookmaker_odds,
    bankroll=5000.0,
    fraction=0.25,
):
    """
    Calculate a fractional Kelly stake.

    probability:
        Win probability as a percentage, for example 69.5

    bookmaker_odds:
        Decimal bookmaker odds, for example 1.80

    bankroll:
        Current bankroll

    fraction:
        Kelly fraction.
        0.25 means quarter Kelly.
    """

    probability = float(probability or 0) / 100
    bookmaker_odds = float(bookmaker_odds or 0)
    bankroll = float(bankroll or 0)
    fraction = float(fraction or 0)

    if probability <= 0:
        return _empty_result("Invalid probability")

    if bookmaker_odds <= 1:
        return _empty_result("Invalid bookmaker odds")

    if bankroll <= 0:
        return _empty_result("Invalid bankroll")

    decimal_profit = bookmaker_odds - 1
    loss_probability = 1 - probability

    full_kelly = (
        (decimal_profit * probability) - loss_probability
    ) / decimal_profit

    if full_kelly <= 0:
        return _empty_result("No positive edge")

    fractional_kelly = full_kelly * fraction
    recommended_stake = bankroll * fractional_kelly

    expected_value_percent = (
        probability * bookmaker_odds - 1
    ) * 100

    if fractional_kelly <= 0.01:
        risk_level = "Low"
    elif fractional_kelly <= 0.025:
        risk_level = "Medium"
    else:
        risk_level = "High"

    return {
        "full_kelly_percent": round(full_kelly * 100, 2),
        "kelly_percent": round(fractional_kelly * 100, 2),
        "recommended_stake": round(recommended_stake, 2),
        "expected_value_percent": round(expected_value_percent, 2),
        "risk_level": risk_level,
        "has_value": True,
        "message": "Positive expected value",
    }


def _empty_result(message):
    return {
        "full_kelly_percent": 0.0,
        "kelly_percent": 0.0,
        "recommended_stake": 0.0,
        "expected_value_percent": 0.0,
        "risk_level": "None",
        "has_value": False,
        "message": message,
    }