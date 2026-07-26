import math
def build_trading_opportunities(result):
    opportunities = []

    recommendation = result["recommendation"]

    opportunities.append(
        {
            "market": recommendation["market"],
            "selection": recommendation["selection"],
            "probability": recommendation["probability"],
            "fair_odds": recommendation["fair_odds"],
            "minimum_odds": math.ceil(
                recommendation["fair_odds"] * 1.05 * 100
            ) / 100,
            "confidence": recommendation["confidence"],
        }
    )

    first180 = result["first_180"]

    if first180["player_a"] >= first180["player_b"]:
        selection = result["player_a"]
        probability = round(first180["player_a"] * 100, 1)
    else:
        selection = result["player_b"]
        probability = round(first180["player_b"] * 100, 1)

    fair_odds = round(100 / probability, 2)

    if probability >= 65:
        confidence = "High"
    elif probability >= 58:
        confidence = "Good"
    elif probability >= 52:
        confidence = "Moderate"
    else:
        confidence = "Low"

    opportunities.append(
        {
            "market": "First 180",
            "selection": selection,
            "probability": probability,
            "fair_odds": fair_odds,
            "minimum_odds": math.ceil(fair_odds * 1.05 * 100) / 100,
            "confidence": confidence,
        }
    )

    return opportunities