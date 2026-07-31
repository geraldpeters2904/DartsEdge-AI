from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.db import SessionLocal
from app.services.demo_data_service import demo_summary, load_demo_data, reset_demo_data
from app.templates_config import templates

router = APIRouter()


@router.get("/admin/demo-data")
def demo_data_page(request: Request, message: str = ""):
    db = SessionLocal()
    try:
        return templates.TemplateResponse(
            "demo_data.html",
            {"request": request, "summary": demo_summary(db), "message": message},
        )
    finally:
        db.close()


@router.post("/admin/demo-data/load")
def load_demo_data_route():
    db = SessionLocal()
    try:
        result = load_demo_data(db)
        message = f"Demo data ready: {result['fixtures']} fixtures, {result['players']} players and {result['odds']} prices."
    finally:
        db.close()
    return RedirectResponse(f"/admin/demo-data?message={message}", status_code=303)


@router.post("/admin/demo-data/reset")
def reset_demo_data_route():
    db = SessionLocal()
    try:
        result = reset_demo_data(db)
        message = f"Removed {result['fixtures_deleted']} demo fixtures and {result['odds_deleted']} demo prices."
    finally:
        db.close()
    return RedirectResponse(f"/admin/demo-data?message={message}", status_code=303)


@router.get("/api/demo-data")
def demo_data_api():
    db = SessionLocal()
    try:
        return {"demo": True, **demo_summary(db)}
    finally:
        db.close()
