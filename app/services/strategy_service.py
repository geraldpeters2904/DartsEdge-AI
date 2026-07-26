import json
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from sqlalchemy.orm import Session

from app.models.strategy_profile import StrategyProfile

RULE_SCHEMA_VERSION = 1
STRATEGY_PROFILE_VERSION = 2

BASE_RULES = {
    "rules_schema_version": RULE_SCHEMA_VERSION,
    "mode": "live",
    "decision_rules_enabled": True,
    "enforcement_mode": "shadow",
    "minimum_ev_percent": 0.0,
    "minimum_edge_percent": 5.0,
    "minimum_model_probability": 55.0,
    "minimum_confidence_percent": 60.0,
    "kelly_fraction": 0.50,
    "maximum_portfolio_exposure_percent": 15.0,
    "maximum_stake_percent": 3.0,
    "minimum_sample_size": 0,
    "maximum_decimal_odds": 10.0,
    "allowed_markets": ["match_winner", "most_180s", "handicap"],
    "allowed_competitions": [],
}


def _rules(**overrides) -> Dict:
    result = dict(BASE_RULES)
    result.update(overrides)
    return result


DEFAULT_STRATEGIES = (
    (
        "Default",
        "Balanced rules aligned with the current DartsEdge settings.",
        _rules(),
        True,
    ),
    (
        "Conservative",
        "High-confidence, low-exposure rules with smaller Kelly stakes.",
        _rules(
            minimum_ev_percent=3.0,
            minimum_edge_percent=7.0,
            minimum_model_probability=62.0,
            minimum_confidence_percent=72.0,
            kelly_fraction=0.25,
            maximum_portfolio_exposure_percent=10.0,
            maximum_stake_percent=1.5,
            minimum_sample_size=20,
            maximum_decimal_odds=5.0,
        ),
        False,
    ),
    (
        "Value Hunter",
        "Expected-value-led rules accepting a wider price range when the edge is strong.",
        _rules(
            minimum_ev_percent=5.0,
            minimum_edge_percent=5.0,
            minimum_model_probability=52.0,
            minimum_confidence_percent=58.0,
            kelly_fraction=0.50,
            maximum_portfolio_exposure_percent=18.0,
            maximum_stake_percent=3.0,
            minimum_sample_size=10,
            maximum_decimal_odds=12.0,
        ),
        False,
    ),
    (
        "Paper Trading",
        "Simulation-only rules for evaluating broader signals without live exposure.",
        _rules(
            mode="paper",
            minimum_ev_percent=0.0,
            minimum_edge_percent=2.0,
            minimum_model_probability=50.0,
            minimum_confidence_percent=50.0,
            kelly_fraction=0.25,
            maximum_portfolio_exposure_percent=25.0,
            maximum_stake_percent=2.0,
            minimum_sample_size=0,
            maximum_decimal_odds=20.0,
        ),
        False,
    ),
    (
        "Custom",
        "User-editable strategy shell using balanced validated defaults.",
        _rules(),
        False,
    ),
)

PROFILE_BY_NAME = {name: (description, rules, active) for name, description, rules, active in DEFAULT_STRATEGIES}


@dataclass(frozen=True)
class StrategyDecision:
    qualifies: bool
    status: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    suggested_stake: float
    strategy_name: str
    strategy_version: int
    enforcement_mode: str


def _number(rules: Dict, key: str, minimum: float, maximum: float) -> float:
    try:
        value = float(rules[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number.") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{key} must be between {minimum:g} and {maximum:g}.")
    return value


def _string_list(rules: Dict, key: str) -> list[str]:
    value = rules.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{key} must be a list of non-empty strings.")
    return sorted({item.strip().lower() for item in value})


def validate_rules(rules: Dict) -> Dict:
    if not isinstance(rules, dict):
        raise ValueError("Strategy rules must be a JSON object.")

    merged = dict(BASE_RULES)
    merged.update(rules)

    mode = merged.get("mode")
    if mode not in {"live", "paper"}:
        raise ValueError("Strategy mode must be 'live' or 'paper'.")
    if not isinstance(merged.get("decision_rules_enabled"), bool):
        raise ValueError("decision_rules_enabled must be true or false.")
    if merged.get("enforcement_mode") not in {"shadow", "active"}:
        raise ValueError("enforcement_mode must be 'shadow' or 'active'.")

    merged["rules_schema_version"] = int(merged.get("rules_schema_version", RULE_SCHEMA_VERSION))
    merged["minimum_ev_percent"] = _number(merged, "minimum_ev_percent", -100, 1000)
    merged["minimum_edge_percent"] = _number(merged, "minimum_edge_percent", -100, 100)
    merged["minimum_model_probability"] = _number(merged, "minimum_model_probability", 0, 100)
    merged["minimum_confidence_percent"] = _number(merged, "minimum_confidence_percent", 0, 100)
    merged["kelly_fraction"] = _number(merged, "kelly_fraction", 0, 1)
    merged["maximum_portfolio_exposure_percent"] = _number(
        merged, "maximum_portfolio_exposure_percent", 0, 100
    )
    merged["maximum_stake_percent"] = _number(merged, "maximum_stake_percent", 0, 100)
    merged["minimum_sample_size"] = int(_number(merged, "minimum_sample_size", 0, 1_000_000))
    merged["maximum_decimal_odds"] = _number(merged, "maximum_decimal_odds", 1.01, 1000)
    merged["allowed_markets"] = _string_list(merged, "allowed_markets")
    merged["allowed_competitions"] = _string_list(merged, "allowed_competitions")
    return merged


def strategy_rules(strategy: StrategyProfile) -> Dict:
    try:
        rules = json.loads(strategy.rules_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Strategy '{strategy.name}' contains invalid JSON rules.") from exc
    return validate_rules(rules)


def _upgrade_existing_strategies(db: Session) -> None:
    changed = False
    for strategy in db.query(StrategyProfile).all():
        profile = PROFILE_BY_NAME.get(strategy.name)
        if profile is None:
            continue
        description, defaults, _ = profile
        try:
            current = json.loads(strategy.rules_json or "{}")
        except json.JSONDecodeError:
            current = {}
        if not current.get("decision_rules_enabled") or "minimum_ev_percent" not in current:
            strategy.rules_json = json.dumps(validate_rules(defaults), sort_keys=True)
            strategy.version = max(strategy.version or 1, STRATEGY_PROFILE_VERSION)
            strategy.description = description
            changed = True
    if changed:
        db.commit()


def seed_default_strategies(db: Session) -> None:
    if db.query(StrategyProfile).count() == 0:
        for name, description, rules, active in DEFAULT_STRATEGIES:
            db.add(
                StrategyProfile(
                    name=name,
                    description=description,
                    version=STRATEGY_PROFILE_VERSION,
                    rules_json=json.dumps(validate_rules(rules), sort_keys=True),
                    is_active=active,
                    is_enabled=True,
                    is_system=True,
                )
            )
        db.commit()
    _upgrade_existing_strategies(db)


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


def evaluate_strategy(
    strategy: StrategyProfile,
    *,
    model_probability: float,
    confidence_percent: float,
    expected_value_percent: float,
    edge_percent: float,
    decimal_odds: float,
    bankroll: float,
    raw_kelly_stake: float,
    market: str = "match_winner",
    competition: str = "",
    sample_size: int = 0,
    portfolio_exposure_percent: Optional[float] = None,
) -> StrategyDecision:
    rules = strategy_rules(strategy)
    blockers: list[str] = []
    warnings: list[str] = []

    checks = (
        (expected_value_percent >= rules["minimum_ev_percent"], f"EV is below {rules['minimum_ev_percent']:.1f}%"),
        (edge_percent >= rules["minimum_edge_percent"], f"Edge is below {rules['minimum_edge_percent']:.1f}%"),
        (model_probability >= rules["minimum_model_probability"], f"Model probability is below {rules['minimum_model_probability']:.1f}%"),
        (confidence_percent >= rules["minimum_confidence_percent"], f"Confidence is below {rules['minimum_confidence_percent']:.1f}%"),
        (decimal_odds <= rules["maximum_decimal_odds"], f"Odds exceed {rules['maximum_decimal_odds']:.2f}"),
        (sample_size >= rules["minimum_sample_size"], f"Sample size is below {rules['minimum_sample_size']}"),
    )
    blockers.extend(message for passed, message in checks if not passed)

    normalised_market = market.strip().lower()
    if rules["allowed_markets"] and normalised_market not in rules["allowed_markets"]:
        blockers.append(f"Market '{market}' is not allowed")

    normalised_competition = competition.strip().lower()
    if rules["allowed_competitions"] and normalised_competition not in rules["allowed_competitions"]:
        blockers.append(f"Competition '{competition or 'Unknown'}' is not allowed")

    if portfolio_exposure_percent is None:
        warnings.append("Portfolio exposure was not supplied for this shadow check")
    elif portfolio_exposure_percent > rules["maximum_portfolio_exposure_percent"]:
        blockers.append(
            f"Portfolio exposure exceeds {rules['maximum_portfolio_exposure_percent']:.1f}%"
        )

    stake_cap = max(0.0, float(bankroll) * rules["maximum_stake_percent"] / 100)
    strategy_fraction = rules["kelly_fraction"]
    baseline_fraction = BASE_RULES["kelly_fraction"] or 1.0
    scaled_stake = max(0.0, float(raw_kelly_stake)) * (strategy_fraction / baseline_fraction)
    suggested_stake = round(min(scaled_stake, stake_cap), 2) if not blockers else 0.0

    qualifies = not blockers and bool(rules["decision_rules_enabled"])
    if not rules["decision_rules_enabled"]:
        blockers.append("Decision rules are disabled")
    status = "Qualifies" if qualifies else "Filtered"
    return StrategyDecision(
        qualifies=qualifies,
        status=status,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        suggested_stake=suggested_stake,
        strategy_name=strategy.name,
        strategy_version=strategy.version,
        enforcement_mode=rules["enforcement_mode"],
    )


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
        "mode": rules["mode"],
        "decision_rules_enabled": rules["decision_rules_enabled"],
        "enforcement_mode": rules["enforcement_mode"],
        "rules": rules,
    }


def get_strategy(db: Session, strategy_id: int) -> StrategyProfile:
    strategy = db.query(StrategyProfile).filter(StrategyProfile.id == strategy_id).first()
    if strategy is None:
        raise ValueError("Strategy not found.")
    return strategy


def get_latest_strategy_version(db: Session, strategy_uuid: str) -> StrategyProfile:
    strategy = (
        db.query(StrategyProfile)
        .filter(StrategyProfile.strategy_uuid == strategy_uuid)
        .order_by(StrategyProfile.version.desc())
        .first()
    )
    if strategy is None:
        raise ValueError("Strategy not found.")
    return strategy


def strategy_history(db: Session, strategy_uuid: str) -> list[StrategyProfile]:
    return (
        db.query(StrategyProfile)
        .filter(StrategyProfile.strategy_uuid == strategy_uuid)
        .order_by(StrategyProfile.version.desc())
        .all()
    )


def create_strategy(
    db: Session,
    *,
    name: str,
    description: str,
    rules: Dict,
    mode: Optional[str] = None,
    activate: bool = False,
) -> StrategyProfile:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Strategy name is required.")
    validated = validate_rules({**rules, **({"mode": mode} if mode else {})})
    strategy = StrategyProfile(
        name=clean_name,
        description=description.strip(),
        version=1,
        rules_json=json.dumps(validated, sort_keys=True),
        is_active=False,
        is_enabled=True,
        is_system=False,
    )
    db.add(strategy)
    db.flush()
    if activate:
        db.query(StrategyProfile).update({StrategyProfile.is_active: False}, synchronize_session=False)
        strategy.is_active = True
    db.commit()
    db.refresh(strategy)
    return strategy


def update_strategy(
    db: Session,
    strategy_id: int,
    *,
    name: str,
    description: str,
    rules: Dict,
) -> StrategyProfile:
    current = get_strategy(db, strategy_id)
    validated = validate_rules(rules)
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Strategy name is required.")
    # Versioned edits are append-only: preserve the old row and create a new version.
    was_active = bool(current.is_active)
    current.is_active = False
    current.is_enabled = False
    replacement = StrategyProfile(
        strategy_uuid=current.strategy_uuid,
        name=clean_name,
        description=description.strip(),
        version=current.version + 1,
        rules_json=json.dumps(validated, sort_keys=True),
        is_active=bool(current.is_active),
        is_enabled=True,
        is_system=current.is_system,
    )
    replacement.is_active = was_active
    db.add(replacement)
    db.commit()
    db.refresh(replacement)
    return replacement


def duplicate_strategy(db: Session, strategy_id: int, *, name: Optional[str] = None) -> StrategyProfile:
    source = get_strategy(db, strategy_id)
    return create_strategy(
        db,
        name=(name or f"{source.name} Copy"),
        description=f"Copy of {source.name}. {source.description}".strip(),
        rules=strategy_rules(source),
        activate=False,
    )


def set_strategy_enabled(db: Session, strategy_id: int, enabled: bool) -> StrategyProfile:
    strategy = get_strategy(db, strategy_id)
    if strategy.is_system and not enabled:
        raise ValueError("System strategies cannot be disabled.")
    if strategy.is_active and not enabled:
        raise ValueError("The active strategy cannot be disabled.")
    strategy.is_enabled = enabled
    db.commit()
    db.refresh(strategy)
    return strategy


def export_strategy(strategy: StrategyProfile) -> dict:
    return {
        "format": "dartsedge-strategy",
        "format_version": 1,
        "name": strategy.name,
        "description": strategy.description,
        "source_uuid": strategy.strategy_uuid,
        "source_version": strategy.version,
        "rules": strategy_rules(strategy),
    }


def import_strategy(db: Session, payload: Dict, *, activate: bool = False) -> StrategyProfile:
    if not isinstance(payload, dict) or payload.get("format") != "dartsedge-strategy":
        raise ValueError("Unsupported strategy import format.")
    return create_strategy(
        db,
        name=str(payload.get("name", "Imported Strategy")) + " (Imported)",
        description=str(payload.get("description", "Imported strategy")),
        rules=payload.get("rules", {}),
        activate=activate,
    )
