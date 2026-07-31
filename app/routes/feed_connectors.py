from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.db import SessionLocal
from app.services.feed_connector_service import FeedConnectorService
from app.templates_config import templates

router = APIRouter()


@router.get("/feed-settings")
def feed_settings(request: Request, days: int = 7):
    db = SessionLocal()
    try:
        service = FeedConnectorService(db)
        preview = error = None
        if request.query_params.get("preview") == "1":
            try:
                preview = service.preview(days=days)
            except Exception as exc:
                error = str(exc)
        return templates.TemplateResponse(request, "feed_settings.html", {
            "config": service.get(), "types": service.registry.types(), "history": service.history(),
            "preview": preview, "error": error, "days": days, "message": request.query_params.get("message"),
        })
    finally:
        db.close()


@router.post("/feed-settings/save")
def save_feed(name: str = Form(...), connector_type: str = Form(...), feed_url: str = Form(""),
              auth_token: str = Form(""), enabled: bool = Form(False), competitions: str = Form(""),
              timeout_seconds: int = Form(15), retry_count: int = Form(2),
              refresh_interval_minutes: int = Form(60)):
    db = SessionLocal()
    try:
        FeedConnectorService(db).save(name=name, connector_type=connector_type, feed_url=feed_url,
            auth_token=auth_token, enabled=enabled, competitions=competitions, timeout_seconds=timeout_seconds,
            retry_count=retry_count, refresh_interval_minutes=refresh_interval_minutes)
        return RedirectResponse("/feed-settings?message=Settings saved", status_code=303)
    finally:
        db.close()


@router.post("/feed-settings/test")
def test_feed():
    db = SessionLocal()
    try:
        result = FeedConnectorService(db).test_connection()
        return RedirectResponse(f"/feed-settings?message={result.status}: {result.detail}", status_code=303)
    finally:
        db.close()


@router.post("/feed-settings/sync")
def sync_feed(days: int = Form(7)):
    db = SessionLocal()
    try:
        result = FeedConnectorService(db).sync(days=days)
        message = f"Imported {result['created']} fixtures; {result['existing']} already existed"
        return RedirectResponse(f"/feed-settings?message={message}", status_code=303)
    finally:
        db.close()


@router.get("/api/feed-status")
def feed_status():
    db = SessionLocal()
    try:
        return FeedConnectorService(db).diagnostics()
    finally:
        db.close()
