def calculate_trade_rating(opportunity):
    """
    Calculate a trade rating (0-100) from an opportunity.
    """

    probability = float(opportunity.get("probability", 0))
    fair_odds = float(opportunity.get("fair_odds", 0))
    minimum_odds = float(opportunity.get("minimum_odds", 0))
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

    # Value score
    if minimum_odds > fair_odds:
        value_edge = ((minimum_odds - fair_odds) / fair_odds) * 100
    else:
        value_edge = 0

    score = (
        probability * 0.45 +
        confidence_score * 0.30 +
        min(value_edge * 5, 25)
    )

    score = round(min(score, 100), 1)

    if score >= 90:
        stars = 5
        grade = "Elite"
    elif score >= 80:
        stars = 4
        grade = "Strong"
    elif score >= 70:
        stars = 3
        grade = "Good"
    elif score >= 60:
        stars = 2
        grade = "Speculative"
    else:
        stars = 1
        grade = "Pass"

    return {
        "score": score,
        "stars": stars,
        "grade": grade,
        "value_edge": round(value_edge, 2),
    }