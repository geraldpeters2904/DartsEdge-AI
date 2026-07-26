from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.prediction_audit import PredictionAudit
from app.models.prediction_audit_outcome import PredictionAuditOutcome


@dataclass(frozen=True)
class ModelMetrics:
    name: str
    settled: int
    correct: int
    accuracy: Optional[float]
    brier: Optional[float]
    calibration_error: Optional[float]


def record_outcome(db: Session, audit_uuid: str, actual_winner: str, source: str = "manual") -> PredictionAuditOutcome:
    audit = db.query(PredictionAudit).filter(PredictionAudit.audit_uuid == audit_uuid).first()
    if audit is None:
        raise ValueError("Prediction audit not found")
    winner = actual_winner.strip()
    if winner not in {audit.player_a, audit.player_b}:
        raise ValueError("Actual winner must match one of the audited players")
    event = PredictionAuditOutcome(audit_id=audit.id, actual_winner=winner, source=source)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def latest_outcomes(db: Session) -> Dict[int, PredictionAuditOutcome]:
    rows = db.query(PredictionAuditOutcome).order_by(PredictionAuditOutcome.recorded_at.asc(), PredictionAuditOutcome.id.asc()).all()
    return {row.audit_id: row for row in rows}


def _metrics(name: str, rows: Iterable[dict], probability_key: str) -> ModelMetrics:
    usable = [row for row in rows if row.get(probability_key) is not None]
    if not usable:
        return ModelMetrics(name, 0, 0, None, None, None)
    correct = 0
    brier_total = 0.0
    buckets: Dict[int, List[tuple]] = {}
    for row in usable:
        p_a = float(row[probability_key])
        actual_a = 1.0 if row["actual_winner"] == row["player_a"] else 0.0
        predicted = row["player_a"] if p_a >= 0.5 else row["player_b"]
        correct += int(predicted == row["actual_winner"])
        brier_total += (p_a - actual_a) ** 2
        confidence = max(p_a, 1.0 - p_a)
        bucket = min(9, int(confidence * 10))
        buckets.setdefault(bucket, []).append((confidence, 1.0 if predicted == row["actual_winner"] else 0.0))
    calibration = 0.0
    total = len(usable)
    for values in buckets.values():
        mean_confidence = sum(v[0] for v in values) / len(values)
        mean_accuracy = sum(v[1] for v in values) / len(values)
        calibration += (len(values) / total) * abs(mean_confidence - mean_accuracy)
    return ModelMetrics(
        name=name,
        settled=total,
        correct=correct,
        accuracy=round(correct / total, 4),
        brier=round(brier_total / total, 4),
        calibration_error=round(calibration, 4),
    )


def comparison_rows(db: Session, limit: int = 250) -> List[dict]:
    outcomes = latest_outcomes(db)
    audits = db.query(PredictionAudit).order_by(PredictionAudit.created_at.desc()).limit(limit).all()
    rows: List[dict] = []
    for audit in audits:
        outcome = outcomes.get(audit.id)
        legacy_pick = audit.player_a if audit.legacy_probability_a >= 0.5 else audit.player_b
        shadow_pick = None
        if audit.intelligence_probability_a is not None:
            shadow_pick = audit.player_a if audit.intelligence_probability_a >= 0.5 else audit.player_b
        winner_model = "Unsettled"
        if outcome:
            legacy_ok = legacy_pick == outcome.actual_winner
            shadow_ok = shadow_pick == outcome.actual_winner if shadow_pick else False
            if legacy_ok and shadow_ok:
                winner_model = "Tie"
            elif legacy_ok:
                winner_model = "Legacy"
            elif shadow_ok:
                winner_model = "Intelligence"
            else:
                winner_model = "Neither"
        rows.append({
            "audit": audit,
            "actual_winner": outcome.actual_winner if outcome else None,
            "legacy_pick": legacy_pick,
            "shadow_pick": shadow_pick,
            "winner_model": winner_model,
            "legacy_probability_a": audit.legacy_probability_a,
            "intelligence_probability_a": audit.intelligence_probability_a,
            "player_a": audit.player_a,
            "player_b": audit.player_b,
        })
    return rows


def build_shadow_comparison(db: Session, limit: int = 250) -> dict:
    rows = comparison_rows(db, limit=limit)
    settled = [row for row in rows if row["actual_winner"]]
    legacy = _metrics("Legacy", settled, "legacy_probability_a")
    intelligence = _metrics("Player Intelligence", settled, "intelligence_probability_a")
    leader = "Insufficient data"
    if legacy.settled and intelligence.settled:
        if intelligence.brier < legacy.brier:
            leader = "Player Intelligence"
        elif legacy.brier < intelligence.brier:
            leader = "Legacy"
        else:
            leader = "Tie"
    accuracy_delta = None
    if legacy.accuracy is not None and intelligence.accuracy is not None:
        accuracy_delta = round(intelligence.accuracy - legacy.accuracy, 4)
    return {
        "rows": rows,
        "settled_count": len(settled),
        "unsettled_count": len(rows) - len(settled),
        "legacy": legacy,
        "intelligence": intelligence,
        "leader": leader,
        "accuracy_delta": accuracy_delta,
        "minimum_sample": 25,
        "sample_ready": len(settled) >= 25,
    }
