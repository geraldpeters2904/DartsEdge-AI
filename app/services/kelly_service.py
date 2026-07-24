from typing import Any, Dict, Optional


def calculate_kelly_stake(
    probability: float,
    bookmaker_odds: float,
    bankroll: float,
    fraction: float,
    max_daily_risk_percent: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculate a fractional Kelly stake.

    Args:
        probability:
            Win probability as a percentage.
            Example: 69.5 means a 69.5% predicted chance.

        bookmaker_odds:
            Decimal bookmaker odds.
            Example: 1.80.

        bankroll:
            Current bankroll supplied from application settings.

        fraction:
            Kelly fraction supplied from application settings.
            Example: 0.25 means quarter Kelly.

        max_daily_risk_percent:
            Optional maximum percentage of bankroll that may be
            recommended for this calculation.

            Example: 5.0 limits the stake to 5% of bankroll.

    Returns:
        Dictionary containing the Kelly percentages, recommended stake,
        expected value, risk classification, and explanatory message.
    """

    probability_percent = _to_float(probability)
    bookmaker_odds = _to_float(bookmaker_odds)
    bankroll = _to_float(bankroll)
    fraction = _to_float(fraction)

    if probability_percent <= 0 or probability_percent > 100:
        return _empty_result("Invalid probability")

    if bookmaker_odds <= 1:
        return _empty_result("Invalid bookmaker odds")

    if bankroll <= 0:
        return _empty_result("Invalid bankroll")

    if fraction <= 0 or fraction > 1:
        return _empty_result("Invalid Kelly fraction")

    probability_decimal = probability_percent / 100
    decimal_profit = bookmaker_odds - 1
    loss_probability = 1 - probability_decimal

    full_kelly = (
        (decimal_profit * probability_decimal) - loss_probability
    ) / decimal_profit

    expected_value_percent = (
        probability_decimal * bookmaker_odds - 1
    ) * 100

    if full_kelly <= 0:
        result = _empty_result("No positive edge")
        result["expected_value_percent"] = round(
            expected_value_percent,
            2,
        )
        return result

    fractional_kelly = full_kelly * fraction
    uncapped_stake = bankroll * fractional_kelly
    recommended_stake = uncapped_stake

    stake_capped = False
    maximum_stake = None

    if max_daily_risk_percent is not None:
        max_daily_risk_percent = _to_float(
            max_daily_risk_percent
        )

        if max_daily_risk_percent < 0:
            return _empty_result(
                "Invalid maximum daily risk"
            )

        maximum_stake = bankroll * (
            max_daily_risk_percent / 100
        )

        if recommended_stake > maximum_stake:
            recommended_stake = maximum_stake
            stake_capped = True

    actual_stake_percent = (
        recommended_stake / bankroll
    ) * 100

    risk_level = _calculate_risk_level(
        actual_stake_percent
    )

    if stake_capped:
        message = (
            "Positive expected value. Stake limited by "
            "maximum daily risk setting."
        )
    else:
        message = "Positive expected value"

    return {
        "full_kelly_percent": round(
            full_kelly * 100,
            2,
        ),
        "kelly_percent": round(
            fractional_kelly * 100,
            2,
        ),
        "actual_stake_percent": round(
            actual_stake_percent,
            2,
        ),
        "recommended_stake": round(
            recommended_stake,
            2,
        ),
        "uncapped_stake": round(
            uncapped_stake,
            2,
        ),
        "maximum_stake": (
            round(maximum_stake, 2)
            if maximum_stake is not None
            else None
        ),
        "expected_value_percent": round(
            expected_value_percent,
            2,
        ),
        "risk_level": risk_level,
        "stake_capped": stake_capped,
        "has_value": True,
        "message": message,
    }


def _calculate_risk_level(
    stake_percent: float,
) -> str:
    """
    Classify risk using the actual percentage of bankroll staked.
    """

    if stake_percent <= 1:
        return "Low"

    if stake_percent <= 2.5:
        return "Medium"

    return "High"


def _to_float(value: Any) -> float:
    """
    Convert a supplied value safely to float.
    """

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _empty_result(message: str) -> Dict[str, Any]:
    return {
        "full_kelly_percent": 0.0,
        "kelly_percent": 0.0,
        "actual_stake_percent": 0.0,
        "recommended_stake": 0.0,
        "uncapped_stake": 0.0,
        "maximum_stake": None,
        "expected_value_percent": 0.0,
        "risk_level": "None",
        "stake_capped": False,
        "has_value": False,
        "message": message,
    }