import csv
import io
import json
import math
import uuid
from datetime import date, datetime, time
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from app.models.prediction_audit import PredictionAudit
from app.version import VERSION

MODEL_VERSION = "player-intelligence-shadow-0.2"


def _json_default(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _shadow_probability(rating_a: Optional[float], rating_b: Optional[float]) -> Optional[float]:
    if rating_a is None or rating_b is None:
        return None
    # A restrained logistic mapping keeps shadow estimates comparable without
    # allowing the experimental model to affect official recommendations.
    probability = 1.0 / (1.0 + math.exp(-(float(rating_a) - float(rating_b)) / 18.0))
    return round(max(0.05, min(0.95, probability)), 4)


def create_prediction_audit(
    db: Session,
    result: Dict[str, Any],
    *,
    prediction_id: Optional[int] = None,
    source: str = "prediction-centre",
    tournament: Optional[str] = None,
) -> PredictionAudit:
    """Append one immutable prediction snapshot and return it."""
    explainability = result.get("explainability") or {}
    profile = explainability.get("profile") or {}
    comparison = result.get("intelligence_comparison") or {}

    rating_a = None
    rating_b = None
    if explainability:
        selection = explainability.get("selection")
        if selection == result.get("player_a"):
            rating_a = explainability.get("selection_intelligence_rating")
            rating_b = explainability.get("opponent_intelligence_rating")
        else:
            rating_b = explainability.get("selection_intelligence_rating")
            rating_a = explainability.get("opponent_intelligence_rating")
    if comparison:
        rating_a = (comparison.get("player_a") or {}).get("rating", rating_a)
        rating_b = (comparison.get("player_b") or {}).get("rating", rating_b)

    official_selection = (
        (result.get("recommendation") or {}).get("selection")
        or explainability.get("selection")
        or (result.get("player_a") if result.get("win_prob_a", 0.5) >= 0.5 else result.get("player_b"))
    )
    probability_a = float(result.get("win_prob_a") or 0.5)
    official_probability = probability_a if official_selection == result.get("player_a") else 1.0 - probability_a

    snapshot = {
        "schema_version": "1.0",
        "prediction_id": prediction_id,
        "players": {"player_a": result.get("player_a"), "player_b": result.get("player_b")},
        "official": {
            "selection": official_selection,
            "probability": round(official_probability, 4),
            "probability_a": round(probability_a, 4),
            "probability_b": round(1.0 - probability_a, 4),
            "recommendation": result.get("recommendation"),
            "confidence": result.get("confidence"),
        },
        "shadow": {
            "model_version": MODEL_VERSION,
            "profile": profile,
            "rating_a": rating_a,
            "rating_b": rating_b,
            "probability_a": _shadow_probability(rating_a, rating_b),
            "explainability": explainability,
        },
        "inputs": {
            "profile_a": result.get("profile_a"),
            "profile_b": result.get("profile_b"),
            "head_to_head": result.get("head_to_head"),
            "prediction_factors": result.get("prediction_factors"),
        },
    }

    explanation_confidence = explainability.get("explanation_confidence") or {}
    record = PredictionAudit(
        audit_uuid=str(uuid.uuid4()),
        prediction_id=prediction_id,
        source=source,
        tournament=tournament,
        player_a=str(result.get("player_a") or ""),
        player_b=str(result.get("player_b") or ""),
        official_selection=str(official_selection or ""),
        official_probability=round(official_probability, 4),
        legacy_probability_a=round(probability_a, 4),
        intelligence_probability_a=_shadow_probability(rating_a, rating_b),
        prediction_confidence=explainability.get("prediction_confidence"),
        explanation_confidence=explanation_confidence.get("label"),
        profile_name=profile.get("name"),
        profile_version=profile.get("version"),
        model_version=MODEL_VERSION,
        application_version=VERSION,
        shadow_mode=True,
        intelligence_rating_a=rating_a,
        intelligence_rating_b=rating_b,
        snapshot_json=json.dumps(snapshot, sort_keys=True, default=_json_default),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_audit(db: Session, audit_uuid: str) -> Optional[PredictionAudit]:
    return db.query(PredictionAudit).filter(PredictionAudit.audit_uuid == audit_uuid).first()


def list_audits(
    db: Session,
    *,
    player: Optional[str] = None,
    profile: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = 250,
) -> Iterable[PredictionAudit]:
    query = db.query(PredictionAudit)
    if player:
        pattern = f"%{player.strip()}%"
        query = query.filter(
            (PredictionAudit.player_a.ilike(pattern))
            | (PredictionAudit.player_b.ilike(pattern))
        )
    if profile:
        query = query.filter(PredictionAudit.profile_name == profile)
    if source:
        query = query.filter(PredictionAudit.source == source)
    if date_from:
        query = query.filter(PredictionAudit.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        query = query.filter(PredictionAudit.created_at <= datetime.combine(date_to, time.max))
    return query.order_by(PredictionAudit.created_at.desc()).limit(max(1, min(limit, 1000))).all()


def audit_snapshot(record: PredictionAudit) -> Dict[str, Any]:
    return json.loads(record.snapshot_json)


def audits_csv(records: Iterable[PredictionAudit]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "audit_uuid", "created_at", "source", "player_a", "player_b",
        "official_selection", "official_probability", "legacy_probability_a",
        "intelligence_probability_a", "profile_name", "profile_version",
        "prediction_confidence", "explanation_confidence", "model_version",
        "application_version",
    ])
    for row in records:
        writer.writerow([
            row.audit_uuid, row.created_at.isoformat(), row.source, row.player_a,
            row.player_b, row.official_selection, row.official_probability,
            row.legacy_probability_a, row.intelligence_probability_a,
            row.profile_name, row.profile_version, row.prediction_confidence,
            row.explanation_confidence, row.model_version, row.application_version,
        ])
    return output.getvalue()
