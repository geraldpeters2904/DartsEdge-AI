from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.prediction_audit import PredictionAudit
from app.services.shadow_comparison_service import latest_outcomes


def _safe_rate(numerator: float, denominator: int) -> Optional[float]:
    return round(numerator / denominator, 4) if denominator else None


def _evaluate(rows: Iterable[dict], probability_key: str) -> dict:
    usable = [r for r in rows if r.get(probability_key) is not None]
    if not usable:
        return {"settled": 0, "correct": 0, "accuracy": None, "brier": None, "calibration_error": None}
    correct = 0
    brier = 0.0
    buckets: Dict[int, List[tuple]] = defaultdict(list)
    for row in usable:
        p_a = float(row[probability_key])
        actual_a = 1.0 if row["actual_winner"] == row["player_a"] else 0.0
        pick = row["player_a"] if p_a >= 0.5 else row["player_b"]
        hit = 1.0 if pick == row["actual_winner"] else 0.0
        correct += int(hit)
        brier += (p_a - actual_a) ** 2
        confidence = max(p_a, 1.0 - p_a)
        buckets[min(9, int(confidence * 10))].append((confidence, hit))
    calibration = 0.0
    total = len(usable)
    for values in buckets.values():
        mean_conf = sum(v[0] for v in values) / len(values)
        mean_hit = sum(v[1] for v in values) / len(values)
        calibration += (len(values) / total) * abs(mean_conf - mean_hit)
    return {
        "settled": total,
        "correct": correct,
        "accuracy": _safe_rate(correct, total),
        "brier": round(brier / total, 4),
        "calibration_error": round(calibration, 4),
    }


def _settled_rows(db: Session, limit: int = 5000) -> List[dict]:
    outcomes = latest_outcomes(db)
    audits = db.query(PredictionAudit).order_by(PredictionAudit.created_at.desc()).limit(limit).all()
    rows = []
    for audit in audits:
        outcome = outcomes.get(audit.id)
        if not outcome:
            continue
        rows.append({
            "audit": audit,
            "player_a": audit.player_a,
            "player_b": audit.player_b,
            "actual_winner": outcome.actual_winner,
            "legacy_probability_a": audit.legacy_probability_a,
            "intelligence_probability_a": audit.intelligence_probability_a,
            "profile_name": audit.profile_name or "Unspecified",
            "profile_version": audit.profile_version,
            "tournament": audit.tournament or "Unspecified",
            "prediction_confidence": audit.prediction_confidence or "Unspecified",
        })
    return rows


def _group_metrics(rows: List[dict], key: str, probability_key: str) -> List[dict]:
    groups: Dict[str, List[dict]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key) or "Unspecified")].append(row)
    result = []
    for name, items in groups.items():
        metrics = _evaluate(items, probability_key)
        result.append({"name": name, **metrics})
    return sorted(result, key=lambda r: (-r["settled"], r["name"]))


def _calibration_bands(rows: List[dict], probability_key: str) -> List[dict]:
    bands = [(0.50, 0.59), (0.60, 0.69), (0.70, 0.79), (0.80, 0.89), (0.90, 1.00)]
    output = []
    for low, high in bands:
        selected = []
        for row in rows:
            value = row.get(probability_key)
            if value is None:
                continue
            confidence = max(float(value), 1.0 - float(value))
            if low <= confidence <= high + 1e-9:
                selected.append(row)
        metrics = _evaluate(selected, probability_key)
        output.append({"label": f"{int(low*100)}–{int(high*100)}%", **metrics})
    return output


def build_model_performance_lab(db: Session) -> dict:
    rows = _settled_rows(db)
    legacy = _evaluate(rows, "legacy_probability_a")
    intelligence = _evaluate(rows, "intelligence_probability_a")
    leaderboard = [
        {"name": "Legacy", **legacy},
        {"name": "Player Intelligence", **intelligence},
    ]
    leaderboard.sort(key=lambda x: (x["brier"] is None, x["brier"] if x["brier"] is not None else 99))

    recent = rows[:25]
    prior = rows[25:50]
    recent_metrics = _evaluate(recent, "intelligence_probability_a")
    prior_metrics = _evaluate(prior, "intelligence_probability_a")
    drift = None
    if recent_metrics["accuracy"] is not None and prior_metrics["accuracy"] is not None:
        drift = round(recent_metrics["accuracy"] - prior_metrics["accuracy"], 4)

    return {
        "settled_count": len(rows),
        "sample_ready": len(rows) >= 25,
        "minimum_sample": 25,
        "leaderboard": leaderboard,
        "profile_metrics": _group_metrics(rows, "profile_name", "intelligence_probability_a"),
        "tournament_metrics": _group_metrics(rows, "tournament", "intelligence_probability_a")[:12],
        "confidence_metrics": _group_metrics(rows, "prediction_confidence", "legacy_probability_a"),
        "calibration_bands": _calibration_bands(rows, "intelligence_probability_a"),
        "recent_metrics": recent_metrics,
        "prior_metrics": prior_metrics,
        "accuracy_drift": drift,
    }
