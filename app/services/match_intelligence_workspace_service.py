from __future__ import annotations

from typing import Any, Dict

from app.models.match import Match
from app.services.daily_briefing_service import _value_opportunities
from app.services.player_profile_service import get_player_profile
from app.services.head_to_head_service import get_head_to_head
from app.services.match_engine import win_probability
from app.services.prediction_pipeline import build_prediction
from app.services.strategy_service import get_active_strategy, strategy_summary


def _normalise(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _fixture_key(player_a: str, player_b: str) -> frozenset[str]:
    return frozenset((_normalise(player_a), _normalise(player_b)))


def _matched_value(db, fixture: Match):
    key = _fixture_key(fixture.player_a, fixture.player_b)
    for row in _value_opportunities(db, limit=100):
        if row.get("match_id") == fixture.id:
            return row
        if _fixture_key(row.get("player_a", ""), row.get("player_b", "")) == key:
            return row
    return None


def build_match_intelligence(db, fixture_id: int) -> Dict[str, Any] | None:
    fixture = db.query(Match).filter(Match.id == fixture_id).first()
    if not fixture:
        return None

    profile_a = get_player_profile(db, fixture.player_a)
    profile_b = get_player_profile(db, fixture.player_b)
    prediction_error = None
    try:
        prediction = build_prediction(db, fixture.player_a, fixture.player_b)
    except (ArithmeticError, ValueError, TypeError) as exc:
        prediction = None
        prediction_error = str(exc)

    if prediction is None and profile_a and profile_b:
        probability_a = win_probability(profile_a["elo"], profile_b["elo"])
        prediction = {
            "player_a": fixture.player_a,
            "player_b": fixture.player_b,
            "win_prob_a": round(probability_a, 3),
            "win_prob_b": round(1 - probability_a, 3),
            "head_to_head": get_head_to_head(db, fixture.player_a, fixture.player_b),
            "prediction_factors": [],
            "confidence": {},
            "confidence_breakdown": {},
            "explainability": {},
            "recommendation": {},
            "explanation": None,
            "partial": True,
        }
    try:
        value = _matched_value(db, fixture)
    except (ArithmeticError, ValueError, TypeError):
        value = None
    active_strategy = strategy_summary(get_active_strategy(db))

    if prediction:
        selected_player = (
            fixture.player_a
            if prediction["win_prob_a"] >= prediction["win_prob_b"]
            else fixture.player_b
        )
        selected_probability = max(
            prediction["win_prob_a"], prediction["win_prob_b"]
        ) * 100
        confidence = prediction.get("confidence_breakdown") or prediction.get("confidence") or {}
        explainability = prediction.get("explainability") or {}
        h2h = prediction.get("head_to_head") or {}
        factors = prediction.get("prediction_factors") or []
        recommendation = prediction.get("recommendation") or {}
    else:
        selected_player = None
        selected_probability = None
        confidence = {}
        explainability = {}
        h2h = {}
        factors = []
        recommendation = {}

    return {
        "fixture": fixture,
        "prediction": prediction,
        "selected_player": selected_player,
        "selected_probability": round(selected_probability, 1) if selected_probability is not None else None,
        "profile_a": profile_a,
        "profile_b": profile_b,
        "head_to_head": h2h,
        "factors": factors,
        "confidence": confidence,
        "explainability": explainability,
        "recommendation": recommendation,
        "value": value,
        "assessment": value.get("assessment") if value else None,
        "price": value.get("price") if value else None,
        "active_strategy": active_strategy,
        "prediction_error": prediction_error,
        "decision_engine_active": (
            active_strategy["decision_rules_enabled"]
            and active_strategy["enforcement_mode"] == "active"
        ),
    }
