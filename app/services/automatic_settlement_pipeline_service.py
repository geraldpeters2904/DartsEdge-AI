from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.services.prediction_settlement_service import (
    settle_completed_prediction_audits,
)


@dataclass(frozen=True)
class SettlementStageResult:
    name: str
    success: bool
    message: str
    error: Optional[str] = None


@dataclass(frozen=True)
class AutomaticSettlementReport:
    audits_scanned: int
    settled: int
    already_settled: int
    missing_match: int
    invalid_match_result: int
    stages: tuple[
        SettlementStageResult,
        ...,
    ]
    success: bool
    message: str


def _run_refresh_stage(
    *,
    name: str,
    callback: Optional[
        Callable[
            [Session],
            object,
        ]
    ],
    db: Session,
) -> SettlementStageResult:
    if callback is None:
        return SettlementStageResult(
            name=name,
            success=True,
            message=(
                "Refresh hook not configured."
            ),
        )

    try:
        result = callback(
            db
        )

        message = (
            getattr(
                result,
                "message",
                None,
            )
            or (
                str(
                    result
                )
                if result
                is not None
                else "Completed."
            )
        )

        return SettlementStageResult(
            name=name,
            success=True,
            message=message,
        )

    except Exception as exc:
        return SettlementStageResult(
            name=name,
            success=False,
            message=(
                f"{name} refresh failed."
            ),
            error=str(
                exc
            ),
        )


def run_automatic_settlement(
    db: Session,
    *,
    source: str = "unified-sync",
    model_version: str = (
        "transparent-v3.3"
    ),
    limit: int = 1000,
    clv_refresh: Optional[
        Callable[
            [Session],
            object,
        ]
    ] = None,
    strategy_refresh: Optional[
        Callable[
            [Session],
            object,
        ]
    ] = None,
    portfolio_refresh: Optional[
        Callable[
            [Session],
            object,
        ]
    ] = None,
    model_health_refresh: Optional[
        Callable[
            [Session],
            object,
        ]
    ] = None,
) -> AutomaticSettlementReport:
    """
    Settle newly completed prediction audits first, then run optional
    downstream refresh hooks.

    The settlement write is authoritative. Downstream analytics are
    fault-isolated: a CLV/model-health refresh failure never rolls back
    or invalidates a correctly recorded match outcome.
    """

    settlement = (
        settle_completed_prediction_audits(
            db,
            source=source,
            model_version=(
                model_version
            ),
            limit=limit,
        )
    )

    stages = []

    if settlement.settled > 0:
        stages.append(
            _run_refresh_stage(
                name="clv",
                callback=(
                    clv_refresh
                ),
                db=db,
            )
        )

        stages.append(
            _run_refresh_stage(
                name="strategy",
                callback=(
                    strategy_refresh
                ),
                db=db,
            )
        )

        stages.append(
            _run_refresh_stage(
                name="portfolio",
                callback=(
                    portfolio_refresh
                ),
                db=db,
            )
        )

        stages.append(
            _run_refresh_stage(
                name="model-health",
                callback=(
                    model_health_refresh
                ),
                db=db,
            )
        )

    failures = [
        stage
        for stage
        in stages
        if not stage.success
    ]

    if settlement.settled == 0:
        message = (
            "No new prediction audits required settlement."
        )
    elif failures:
        message = (
            "Predictions settled; one or more downstream refreshes failed."
        )
    else:
        message = (
            "Predictions settled and downstream refreshes completed."
        )

    return AutomaticSettlementReport(
        audits_scanned=(
            settlement
            .audits_scanned
        ),
        settled=(
            settlement
            .settled
        ),
        already_settled=(
            settlement
            .already_settled
        ),
        missing_match=(
            settlement
            .missing_match
        ),
        invalid_match_result=(
            settlement
            .invalid_match_result
        ),
        stages=tuple(
            stages
        ),
        success=(
            len(
                failures
            )
            == 0
        ),
        message=message,
    )
