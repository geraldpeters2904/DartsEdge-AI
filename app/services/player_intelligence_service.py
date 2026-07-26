import json
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from sqlalchemy.orm import Session

from app.models.intelligence_profile import IntelligenceProfile
from app.services.player_profile_service import get_player_profile

FACTOR_LABELS = {
    "elo": "Elo strength",
    "recent_form": "Recent form",
    "scoring": "Three-dart average",
    "checkout": "Checkout performance",
    "one80_scoring": "180 scoring",
    "opponent_strength": "Opponent strength",
    "head_to_head": "Head-to-head",
    "recency": "Data recency",
    "tournament": "Tournament context",
}

DEFAULT_PROFILES = (
    ("Default", "Balanced general-purpose profile.", {"elo": 30, "recent_form": 20, "scoring": 15, "checkout": 10, "one80_scoring": 10, "opponent_strength": 5, "head_to_head": 5, "recency": 3, "tournament": 2}, True),
    ("Elo Heavy", "Favours established long-term strength.", {"elo": 45, "recent_form": 15, "scoring": 12, "checkout": 8, "one80_scoring": 7, "opponent_strength": 5, "head_to_head": 4, "recency": 2, "tournament": 2}, False),
    ("Form Heavy", "Favours current form and recent scoring.", {"elo": 20, "recent_form": 30, "scoring": 18, "checkout": 10, "one80_scoring": 10, "opponent_strength": 4, "head_to_head": 4, "recency": 3, "tournament": 1}, False),
    ("Experimental", "Reserved for controlled model experiments.", {"elo": 25, "recent_form": 20, "scoring": 18, "checkout": 12, "one80_scoring": 10, "opponent_strength": 5, "head_to_head": 5, "recency": 3, "tournament": 2}, False),
)


def validate_weights(weights: Dict[str, float]) -> None:
    missing = set(FACTOR_LABELS) - set(weights)
    extra = set(weights) - set(FACTOR_LABELS)
    if missing or extra:
        raise ValueError(f"Weight factors must match the supported factors. Missing={sorted(missing)}, extra={sorted(extra)}")
    if any(float(value) < 0 for value in weights.values()):
        raise ValueError("Weights cannot be negative.")
    if abs(sum(float(value) for value in weights.values()) - 100.0) > 0.001:
        raise ValueError("Profile weights must total 100%.")


def seed_default_profiles(db: Session) -> None:
    if db.query(IntelligenceProfile).count():
        return
    for name, description, weights, active in DEFAULT_PROFILES:
        validate_weights(weights)
        db.add(IntelligenceProfile(name=name, version=1, description=description, weights_json=json.dumps(weights, sort_keys=True), is_active=active, is_system=True))
    db.commit()


def profile_weights(profile: IntelligenceProfile) -> Dict[str, float]:
    weights = json.loads(profile.weights_json)
    validate_weights(weights)
    return {key: float(value) for key, value in weights.items()}


def get_active_profile(db: Session) -> IntelligenceProfile:
    seed_default_profiles(db)
    profile = db.query(IntelligenceProfile).filter(IntelligenceProfile.is_active.is_(True)).order_by(IntelligenceProfile.id.asc()).first()
    if profile is None:
        profile = db.query(IntelligenceProfile).order_by(IntelligenceProfile.id.asc()).first()
        profile.is_active = True
        db.commit()
        db.refresh(profile)
    return profile


def list_profiles(db: Session) -> Iterable[IntelligenceProfile]:
    seed_default_profiles(db)
    return db.query(IntelligenceProfile).order_by(IntelligenceProfile.name.asc(), IntelligenceProfile.version.desc()).all()


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def _component_scores(player_profile: dict) -> Dict[str, float]:
    matches = float(player_profile.get("matches") or 0)
    win_pct = float(player_profile.get("win_pct") or 0)
    average = float(player_profile.get("average") or 0)
    checkout = float(player_profile.get("checkout") or 0)
    elo = float(player_profile.get("elo") or 1500)
    form = player_profile.get("form") or {}
    expected_180 = float(form.get("expected") or 0)

    return {
        "elo": _clamp(50 + ((elo - 1500) / 8)),
        "recent_form": _clamp(win_pct),
        "scoring": _clamp((average - 70) * 3.3),
        "checkout": _clamp(checkout * 2 if checkout <= 50 else checkout),
        "one80_scoring": _clamp(expected_180 * 32),
        "opponent_strength": _clamp(50 + ((elo - 1500) / 12)),
        "head_to_head": 50.0,
        "recency": _clamp(35 + min(matches, 30) * 2.15),
        "tournament": 50.0,
    }


def build_player_intelligence(db: Session, player_name: str, profile: Optional[IntelligenceProfile] = None) -> Optional[dict]:
    player = get_player_profile(db, player_name)
    if not player:
        return None
    profile = profile or get_active_profile(db)
    weights = profile_weights(profile)
    scores = _component_scores(player)
    components = []
    total = 0.0
    for key, weight in weights.items():
        score = scores[key]
        contribution = score * (weight / 100.0)
        total += contribution
        components.append({"key": key, "label": FACTOR_LABELS[key], "weight": weight, "score": score, "contribution": round(contribution, 2), "available": key not in {"head_to_head", "tournament"}})
    components.sort(key=lambda item: item["contribution"], reverse=True)
    return {
        "player": player_name,
        "rating": round(total, 1),
        "profile": {"id": profile.id, "name": profile.name, "version": profile.version},
        "components": components,
        "data_matches": player.get("matches", 0),
        "mode": "shadow",
        "official_prediction_unchanged": True,
    }


def compare_player_intelligence(db: Session, player_a: str, player_b: str) -> Optional[dict]:
    active = get_active_profile(db)
    a = build_player_intelligence(db, player_a, active)
    b = build_player_intelligence(db, player_b, active)
    if not a or not b:
        return None
    return {"profile": a["profile"], "player_a": a, "player_b": b, "rating_gap": round(a["rating"] - b["rating"], 1), "shadow_mode": True}
