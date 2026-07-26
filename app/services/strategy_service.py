import json
from typing import Dict, Iterable

from sqlalchemy.orm import Session

from app.models.strategy_profile import StrategyProfile

DEFAULT_STRATEGIES = (
    (
        "Default",
        "Balanced strategy preserving the current DartsEdge decision settings.",
        {"mode": "live", "decision_rules_enabled": False},
        True,
    ),
    (
        "Conservative",
        "High-confidence, lower-exposure strategy reserved for future rule integration.",
        {"mode": "live", "decision_rules_enabled": False},
        False,
    ),
    (
        "Value Hunter",
        "Expected-value-led strategy reserved for future rule integration.",
        {"mode": "live", "decision_rules_enabled": False},
        False,
    ),
    (
        "Paper Trading",
        "Simulation-only strategy for controlled evaluation.",
        {"mode": "paper", "decision_rules_enabled": False},
        False,
    ),
    (
        "Custom",
        "User-editable strategy shell. Editing arrives in a later pack.",
        {"mode": "live", "decision_rules_enabled": False},
        False,
    ),
)


def validate_rules(rules: Dict) -> Dict:
    if not isinstance(rules, dict):
        raise ValueError("Strategy rules must be a JSON object.")
    mode = rules.get("mode", "live")
    if mode not in {"live", "paper"}:
        raise ValueError("Strategy mode must be 'live' or 'paper'.")
    enabled = rules.get("decision_rules_enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("decision_rules_enabled must be true or false.")
    return rules


def strategy_rules(strategy: StrategyProfile) -> Dict:
    rules = json.loads(strategy.rules_json or "{}")
    return validate_rules(rules)


def seed_default_strategies(db: Session) -> None:
    if db.query(StrategyProfile).count() > 0:
        return
    for name, description, rules, active in DEFAULT_STRATEGIES:
        db.add(
            StrategyProfile(
                name=name,
                description=description,
                version=1,
                rules_json=json.dumps(validate_rules(rules), sort_keys=True),
                is_active=active,
                is_enabled=True,
                is_system=True,
            )
        )
    db.commit()


def list_strategies(db: Session) -> Iterable[StrategyProfile]:
    seed_default_strategies(db)
    return db.query(StrategyProfile).order_by(StrategyProfile.name.asc(), StrategyProfile.version.desc()).all()


def get_active_strategy(db: Session) -> StrategyProfile:
    seed_default_strategies(db)
    strategy = (
        db.query(StrategyProfile)
        .filter(StrategyProfile.is_active.is_(True), StrategyProfile.is_enabled.is_(True))
        .order_by(StrategyProfile.id.asc())
        .first()
    )
    if strategy is None:
        strategy = db.query(StrategyProfile).filter(StrategyProfile.is_enabled.is_(True)).order_by(StrategyProfile.id.asc()).first()
        if strategy is None:
            raise RuntimeError("No enabled strategy is available.")
        strategy.is_active = True
        db.commit()
        db.refresh(strategy)
    return strategy


def activate_strategy(db: Session, strategy_id: int) -> StrategyProfile:
    target = db.query(StrategyProfile).filter(StrategyProfile.id == strategy_id).first()
    if target is None:
        raise ValueError("Strategy not found.")
    if not target.is_enabled:
        raise ValueError("Disabled strategies cannot be activated.")
    db.query(StrategyProfile).update({StrategyProfile.is_active: False}, synchronize_session=False)
    target.is_active = True
    db.commit()
    db.refresh(target)
    return target


def strategy_summary(strategy: StrategyProfile) -> dict:
    rules = strategy_rules(strategy)
    return {
        "id": strategy.id,
        "uuid": strategy.strategy_uuid,
        "name": strategy.name,
        "description": strategy.description,
        "version": strategy.version,
        "active": strategy.is_active,
        "enabled": strategy.is_enabled,
        "system": strategy.is_system,
        "mode": rules.get("mode", "live"),
        "decision_rules_enabled": rules.get("decision_rules_enabled", False),
    }
