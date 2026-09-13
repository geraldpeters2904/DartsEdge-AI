import csv
import io
import json
import math
import re
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


def _shadow_probability(
    rating_a: Optional[float],
    rating_b: Optional[float],
) -> Optional[float]:
    if rating_a is None or rating_b is None:
        return None

    probability = 1.0 / (
        1.0
        + math.exp(
            -(
                float(rating_a)
                - float(rating_b)
            )
            / 18.0
        )
    )

    return round(max(0.05, min(0.95, probability)), 4)


def create_prediction_audit(
    db: Session,
    result: Dict[str, Any],
    *,
    prediction_id: Optional[int] = None,
    source: str = "prediction-centre",
    tournament: Optional[str] = None,
) -> PredictionAudit:
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
        or (
            result.get("player_a")
            if result.get("win_prob_a", 0.5) >= 0.5
            else result.get("player_b")
        )
    )

    probability_a = float(result.get("win_prob_a") or 0.5)
    official_probability = (
        probability_a
        if official_selection == result.get("player_a")
        else 1.0 - probability_a
    )

    snapshot = {
        "schema_version": "1.0",
        "prediction_id": prediction_id,
        "players": {
            "player_a": result.get("player_a"),
            "player_b": result.get("player_b"),
        },
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


def create_prediction_context_audit(
    db: Session,
    context,
    *,
    source: str = "prediction-context",
    tournament: Optional[str] = None,
) -> PredictionAudit:
    probability_a = float(context.player_a_probability) / 100.0
    probability_b = float(context.player_b_probability) / 100.0

    official_selection = context.predicted_winner
    official_probability = (
        probability_a
        if official_selection == context.player_a_name
        else probability_b
    )

    confidence_value = float(context.model_confidence)
    if confidence_value >= 75.0:
        confidence_label = "High"
    elif confidence_value >= 60.0:
        confidence_label = "Medium"
    else:
        confidence_label = "Low"

    snapshot = {
        "schema_version": "2.0",
        "match_id": context.match_id,
        "model": {
            "name": context.model_name,
            "version": context.model_version,
            "score": context.model_score,
            "confidence": context.model_confidence,
        },
        "players": {
            "player_a": context.player_a_name,
            "player_b": context.player_b_name,
            "player_a_history_matches": context.player_a_history_matches,
            "player_b_history_matches": context.player_b_history_matches,
        },
        "prediction": {
            "selection": official_selection,
            "probability_a": round(probability_a, 6),
            "probability_b": round(probability_b, 6),
            "official_probability": round(official_probability, 6),
            "explanations": list(context.explanations),
            "contributions": [dict(item) for item in context.contributions],
        },
    }

    model_version = str(context.model_version or "").strip()
    if not model_version:
        raise ValueError("Prediction context model_version is required.")

    version_match = re.search(r"v(\d+)(?:\.(\d+))?", model_version)
    profile_version = None
    if version_match is not None:
        major = int(version_match.group(1))
        minor = version_match.group(2)
        profile_version = (
            major * 10 + int(minor)
            if minor is not None
            else major
        )

    record = PredictionAudit(
        audit_uuid=str(uuid.uuid4()),
        prediction_id=int(context.match_id),
        source=source,
        tournament=tournament,
        player_a=str(context.player_a_name),
        player_b=str(context.player_b_name),
        official_selection=str(official_selection),
        official_probability=round(official_probability, 6),
        legacy_probability_a=round(probability_a, 6),
        intelligence_probability_a=round(probability_a, 6),
        prediction_confidence=confidence_label,
        explanation_confidence=confidence_label,
        profile_name="Transparent",
        profile_version=profile_version,
        model_version=model_version,
        application_version=VERSION,
        shadow_mode=False,
        intelligence_rating_a=None,
        intelligence_rating_b=None,
        snapshot_json=json.dumps(snapshot, sort_keys=True, default=_json_default),
    )

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_or_create_prediction_context_audit(
    db: Session,
    context,
    *,
    source: str = "prediction-centre-auto",
    tournament: Optional[str] = None,
) -> tuple[PredictionAudit, bool]:
    existing = (
        db.query(PredictionAudit)
        .filter(
            PredictionAudit.prediction_id == int(context.match_id),
            PredictionAudit.model_version == str(context.model_version),
            PredictionAudit.shadow_mode.is_(False),
        )
        .order_by(PredictionAudit.created_at.asc())
        .first()
    )

    if existing is not None:
        return existing, False

    return (
        create_prediction_context_audit(
            db,
            context,
            source=source,
            tournament=tournament,
        ),
        True,
    )


def get_audit(db: Session, audit_uuid: str) -> Optional[PredictionAudit]:
    return (
        db.query(PredictionAudit)
        .filter(PredictionAudit.audit_uuid == audit_uuid)
        .first()
    )


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
            PredictionAudit.player_a.ilike(pattern)
            | PredictionAudit.player_b.ilike(pattern)
        )
    if profile:
        query = query.filter(PredictionAudit.profile_name == profile)
    if source:
        query = query.filter(PredictionAudit.source == source)
    if date_from:
        query = query.filter(
            PredictionAudit.created_at >= datetime.combine(date_from, time.min)
        )
    if date_to:
        query = query.filter(
            PredictionAudit.created_at <= datetime.combine(date_to, time.max)
        )
    return (
        query.order_by(PredictionAudit.created_at.desc())
        .limit(max(1, min(limit, 1000)))
        .all()
    )


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
