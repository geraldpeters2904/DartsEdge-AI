from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.player_intelligence_service import compare_player_intelligence


def _confidence_label(probability: float) -> str:
    probability = max(probability, 1.0 - probability)
    if probability >= 0.72:
        return "High"
    if probability >= 0.60:
        return "Medium"
    return "Low"


def _impact_label(gap: float) -> str:
    magnitude = abs(gap)
    if magnitude >= 8:
        return "strong"
    if magnitude >= 3:
        return "moderate"
    return "small"


def _explanation_confidence(components: List[Dict[str, Any]], matches_a: int, matches_b: int) -> Dict[str, Any]:
    total_weight = sum(float(item.get("weight", 0)) for item in components) or 100.0
    available_weight = sum(
        float(item.get("weight", 0))
        for item in components
        if item.get("available", False)
    )
    coverage = round((available_weight / total_weight) * 100, 1)
    sample = min(int(matches_a or 0), int(matches_b or 0))

    if coverage >= 85 and sample >= 20:
        label = "High"
    elif coverage >= 65 and sample >= 8:
        label = "Medium"
    else:
        label = "Low"

    return {
        "label": label,
        "coverage_percent": coverage,
        "minimum_player_matches": sample,
        "message": (
            f"{coverage:.0f}% of the active profile weight is supported by currently "
            f"available factors; the smaller player sample contains {sample} match(es)."
        ),
    }


def build_explanation_from_comparison(
    comparison: Dict[str, Any],
    official_probability_a: float,
) -> Dict[str, Any]:
    player_a = comparison["player_a"]
    player_b = comparison["player_b"]
    favours_a = official_probability_a >= 0.5
    selection = player_a["player"] if favours_a else player_b["player"]
    opponent = player_b["player"] if favours_a else player_a["player"]
    selected_probability = official_probability_a if favours_a else 1.0 - official_probability_a

    components_a = {item["key"]: item for item in player_a["components"]}
    components_b = {item["key"]: item for item in player_b["components"]}
    factors: List[Dict[str, Any]] = []

    for key, item_a in components_a.items():
        item_b = components_b[key]
        raw_gap = float(item_a["score"]) - float(item_b["score"])
        contribution_gap = float(item_a["contribution"]) - float(item_b["contribution"])
        selected_gap = raw_gap if favours_a else -raw_gap
        selected_contribution = contribution_gap if favours_a else -contribution_gap
        available = bool(item_a.get("available") and item_b.get("available"))

        if not available:
            direction = "unavailable"
        elif selected_contribution > 0.05:
            direction = "positive"
        elif selected_contribution < -0.05:
            direction = "negative"
        else:
            direction = "neutral"

        factors.append({
            "key": key,
            "label": item_a["label"],
            "weight": float(item_a["weight"]),
            "selection_score": item_a["score"] if favours_a else item_b["score"],
            "opponent_score": item_b["score"] if favours_a else item_a["score"],
            "score_gap": round(selected_gap, 1),
            "impact": round(selected_contribution, 2),
            "direction": direction,
            "strength": _impact_label(selected_contribution),
            "available": available,
        })

    positives = sorted(
        (item for item in factors if item["direction"] == "positive"),
        key=lambda item: item["impact"],
        reverse=True,
    )
    negatives = sorted(
        (item for item in factors if item["direction"] == "negative"),
        key=lambda item: item["impact"],
    )
    unavailable = [item for item in factors if item["direction"] == "unavailable"]

    explanation_confidence = _explanation_confidence(
        factors,
        player_a.get("data_matches", 0),
        player_b.get("data_matches", 0),
    )

    summary_parts = []
    if positives:
        summary_parts.append(
            f"{positives[0]['label']} provides the largest intelligence-model advantage for {selection}."
        )
    if negatives:
        summary_parts.append(
            f"{negatives[0]['label']} is the main factor working against the selection."
        )
    if unavailable:
        summary_parts.append(
            f"{len(unavailable)} factor(s) currently use neutral placeholders and do not strengthen the case."
        )
    if not summary_parts:
        summary_parts.append("The active intelligence profile finds little separation between the players.")

    return {
        "schema_version": "1.0",
        "mode": "shadow",
        "official_model_unchanged": True,
        "selection": selection,
        "opponent": opponent,
        "official_probability": round(selected_probability * 100, 1),
        "prediction_confidence": _confidence_label(selected_probability),
        "explanation_confidence": explanation_confidence,
        "profile": comparison["profile"],
        "selection_intelligence_rating": player_a["rating"] if favours_a else player_b["rating"],
        "opponent_intelligence_rating": player_b["rating"] if favours_a else player_a["rating"],
        "rating_gap": round(abs(float(comparison["rating_gap"])), 1),
        "positive_factors": positives[:4],
        "negative_factors": negatives[:3],
        "unavailable_factors": unavailable,
        "all_factors": factors,
        "summary": " ".join(summary_parts),
        "disclaimer": (
            "This explanation describes the experimental Player Intelligence shadow model. "
            "The official prediction probability still comes from the existing production model."
        ),
    }


def build_prediction_explainability(
    db: Session,
    player_a: str,
    player_b: str,
    official_probability_a: float,
) -> Optional[Dict[str, Any]]:
    comparison = compare_player_intelligence(db, player_a, player_b)
    if not comparison:
        return None
    return build_explanation_from_comparison(comparison, official_probability_a)
