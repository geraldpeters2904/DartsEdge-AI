from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.historical_import_service import batches
from app.templates_config import templates


router = APIRouter()


SUPPORTED_FILES = (
    {
        "entity_type": "fixtures",
        "filename": "fixtures.csv",
        "label": "Fixtures",
        "description": (
            "Scheduled matches, competition details and participants."
        ),
        "icon": "📅",
    },
    {
        "entity_type": "results",
        "filename": "results.csv",
        "label": "Results",
        "description": (
            "Final scores, winners, first-leg winners and first 180s."
        ),
        "icon": "🏁",
    },
    {
        "entity_type": "statistics",
        "filename": "statistics.csv",
        "label": "Statistics",
        "description": (
            "Player averages, scoring, checkout and leg statistics."
        ),
        "icon": "📊",
    },
    {
        "entity_type": "odds",
        "filename": "odds.csv",
        "label": "Odds",
        "description": (
            "Immutable bookmaker market-price observations."
        ),
        "icon": "💷",
    },
)


COMPETITIONS = (
    ("MODUS", "MODUS Super Series"),
    ("PDC", "Professional Darts Corporation"),
    ("WDF", "World Darts Federation"),
    ("ADC", "Amateur Darts Circuit"),
    ("CDC", "Championship Darts Corporation"),
    ("OTHER", "Other competition"),
)


@router.get("/admin/collector")
def collector_page(
    request: Request,
    db: Session = Depends(get_db),
):
    recent_batches = batches(db, limit=15)

    imported_batches = sum(
        1
        for batch in recent_batches
        if batch.status == "imported"
    )
    rolled_back_batches = sum(
        1
        for batch in recent_batches
        if batch.status == "rolled_back"
    )
    received_records = sum(
        int(batch.received_rows or 0)
        for batch in recent_batches
    )

    return templates.TemplateResponse(
        request,
        "collector.html",
        {
            "supported_files": SUPPORTED_FILES,
            "competitions": COMPETITIONS,
            "batches": recent_batches,
            "message": request.query_params.get("message"),
            "dashboard": {
                "recent_batches": len(recent_batches),
                "imported_batches": imported_batches,
                "rolled_back_batches": rolled_back_batches,
                "received_records": received_records,
            },
        },
    )
