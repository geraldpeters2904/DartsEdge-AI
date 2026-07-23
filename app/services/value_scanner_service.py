def calculate_value_score(opportunity):
    """
    Build one ranking score from the existing trade metrics.

    Expected opportunity fields:
    - probability
    - trade_score
    - kelly_percent
    - expected_value
    - confidence
    """

    probability = float(opportunity.get("probability", 0) or 0)
    trade_score = float(opportunity.get("trade_score", 0) or 0)
    kelly_percent = float(opportunity.get("kelly_percent", 0) or 0)
    expected_value = float(opportunity.get("expected_value", 0) or 0)
    confidence = opportunity.get("confidence", "Low")

    confidence_scores = {
        "Elite": 100,
        "Very Strong": 90,
        "Strong": 80,
        "Good": 70,
        "Moderate": 60,
        "Low": 50,
    }

    confidence_score = confidence_scores.get(confidence, 50)

    # Cap the more volatile inputs so one unusually large value
    # cannot dominate the complete score.
    kelly_component = min(kelly_percent * 10, 100)
    ev_component = min(max(expected_value, 0) * 10, 100)

    value_score = (
        trade_score * 0.35
        + ev_component * 0.25
        + kelly_component * 0.15
        + confidence_score * 0.15
        + probability * 0.10
    )

    value_score = round(min(max(value_score, 0), 100), 1)

    if value_score >= 85:
        signal = "Excellent"
        indicator = "🟢"
    elif value_score >= 70:
        signal = "Consider"
        indicator = "🟡"
    elif value_score >= 55:
        signal = "Speculative"
        indicator = "🟠"
    else:
        signal = "Avoid"
        indicator = "🔴"

    return {
        "value_score": value_score,
        "signal": signal,
        "indicator": indicator,
    }


def rank_opportunities(opportunities):
    """
    Add Value Scanner fields and return opportunities ranked
    from highest value score to lowest.
    """

    ranked = []

    for opportunity in opportunities:
        scan = calculate_value_score(opportunity)

        opportunity["value_score"] = scan["value_score"]
        opportunity["value_signal"] = scan["signal"]
        opportunity["value_indicator"] = scan["indicator"]

        ranked.append(opportunity)

    return sorted(
        ranked,
        key=lambda item: item.get("value_score", 0),
        reverse=True,
    )