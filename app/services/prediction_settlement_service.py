from __future__ import annotations

from dataclasses import dataclass

from app.models.match import Match
from app.models.prediction_audit import PredictionAudit
from app.prediction_config import ACTIVE_PREDICTION_MODEL_NAME
from app.services.shadow_comparison_service import (
    latest_outcomes,
    record_outcome,
)


@dataclass(frozen=True)
class PredictionSettlementReport:
    completed_matches_scanned: int
    audits_scanned: int
    settled: int
    already_settled: int
    missing_match: int
    invalid_match_result: int


def settle_completed_prediction_audits(
    db,
    *,
    source: str = "warehouse-auto",
    model_version: str = ACTIVE_PREDICTION_MODEL_NAME,
    limit: int = 1000,
) -> PredictionSettlementReport:
    safe_limit = max(1, min(int(limit), 5000))

    audits = (
        db.query(PredictionAudit)
        .filter(
            PredictionAudit.model_version == model_version,
            PredictionAudit.prediction_id.isnot(None),
        )
        .order_by(PredictionAudit.created_at.asc())
        .limit(safe_limit)
        .all()
    )

    outcomes = latest_outcomes(db)

    settled = 0
    already_settled = 0
    missing_match = 0
    invalid_match_result = 0
    completed_match_ids = set()

    for audit in audits:
        if audit.id in outcomes:
            already_settled += 1
            continue

        match = (
            db.query(Match)
            .filter(Match.id == audit.prediction_id)
            .first()
        )

        if match is None:
            missing_match += 1
            continue

        if match.status != "completed":
            continue

        completed_match_ids.add(match.id)

        winner = (match.winner or "").strip()

        if winner not in {
            audit.player_a,
            audit.player_b,
        }:
            invalid_match_result += 1
            continue

        record_outcome(
            db,
            audit.audit_uuid,
            winner,
            source=source,
        )
        settled += 1

    return PredictionSettlementReport(
        completed_matches_scanned=len(completed_match_ids),
        audits_scanned=len(audits),
        settled=settled,
        already_settled=already_settled,
        missing_match=missing_match,
        invalid_match_result=invalid_match_result,
    )
