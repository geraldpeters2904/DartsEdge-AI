from fastapi import APIRouter, Request

from app.db import SessionLocal
from app.models.match import Match
from app.templates_config import templates


router = APIRouter()


@router.get("/forward-schedule")
def forward_schedule_page(
    request: Request,
):
    db = SessionLocal()

    try:
        rows = (
            db.query(Match)
            .filter(
                Match.status == "scheduled",
                Match.tournament.ilike("%MODUS%"),
            )
            .order_by(
                Match.date.asc(),
                Match.id.asc(),
            )
            .limit(200)
            .all()
        )

        return templates.TemplateResponse(
            "forward_schedule.html",
            {
                "request": request,
                "rows": rows,
                "row_count": len(
                    rows
                ),
            },
        )
    finally:
        db.close()
