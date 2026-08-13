from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.services.live_operations_centre_service import (
    build_live_ops_summary,
    recent_odds_movements,
)
from app.services.forward_schedule_monitor_service import (
    forward_schedule_monitor,
)
from app.services.fixture_acquisition_readiness_service import (
    build_fixture_acquisition_readiness,
)
from app.services.odds_acquisition_readiness_service import (
    build_odds_acquisition_readiness,
)
from app.services.live_opportunity_pipeline_readiness_service import (
    build_live_opportunity_pipeline_readiness,
)
from app.templates_config import templates


router = APIRouter()


@router.get("/live-operations")
def live_operations_page(
    request: Request,
):
    db = SessionLocal()

    try:
        summary = (
            build_live_ops_summary(
                db
            )
        )

        movements = (
            recent_odds_movements(
                db,
                limit=25,
            )
        )

        forward_monitor = (
            forward_schedule_monitor.status()
        )

        fixture_acquisition = (
            build_fixture_acquisition_readiness(
                db,
                monitor_status=(
                    forward_monitor
                ),
            )
        )

        odds_acquisition = (
            build_odds_acquisition_readiness(
                db
            )
        )

        live_pipeline = (
            build_live_opportunity_pipeline_readiness(
                db
            )
        )

        return templates.TemplateResponse(
            "live_operations.html",
            {
                "request": request,
                "summary": summary,
                "movements": movements,
                "forward_monitor": (
                    forward_monitor
                ),
                "fixture_acquisition": (
                    fixture_acquisition
                ),
                "odds_acquisition": (
                    odds_acquisition
                ),
                "live_pipeline": (
                    live_pipeline
                ),
                "discovery_targets": (
                    forward_monitor
                    .discovery_targets
                ),
            },
        )

    finally:
        db.close()
