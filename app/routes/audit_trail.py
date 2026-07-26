from datetime import date
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.db import SessionLocal
from app.models.prediction_audit import PredictionAudit
from app.services.prediction_audit_service import audit_snapshot, audits_csv, get_audit, list_audits
from app.templates_config import templates

router = APIRouter()


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@router.get("/audit-trail")
def audit_trail_page(
    request: Request,
    player: Optional[str] = None,
    profile: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    db = SessionLocal()
    try:
        records = list_audits(
            db,
            player=player,
            profile=profile,
            source=source,
            date_from=_parse_date(date_from),
            date_to=_parse_date(date_to),
        )
        profiles = sorted({row.profile_name for row in db.query(PredictionAudit).all() if row.profile_name})
        return templates.TemplateResponse("audit_trail.html", {
            "request": request,
            "records": records,
            "profiles": profiles,
            "filters": {"player": player or "", "profile": profile or "", "source": source or "", "date_from": date_from or "", "date_to": date_to or ""},
        })
    finally:
        db.close()


@router.get("/audit-trail/export.csv")
def audit_trail_export(
    player: Optional[str] = None,
    profile: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    db = SessionLocal()
    try:
        content = audits_csv(list_audits(db, player=player, profile=profile, source=source, date_from=_parse_date(date_from), date_to=_parse_date(date_to), limit=1000))
        return Response(content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=dartsedge_prediction_audit.csv"})
    finally:
        db.close()


@router.get("/audit-trail/{audit_uuid}")
def audit_detail(request: Request, audit_uuid: str):
    db = SessionLocal()
    try:
        record = get_audit(db, audit_uuid)
        if not record:
            return templates.TemplateResponse("audit_detail.html", {"request": request, "record": None, "snapshot": None}, status_code=404)
        return templates.TemplateResponse("audit_detail.html", {"request": request, "record": record, "snapshot": audit_snapshot(record)})
    finally:
        db.close()
