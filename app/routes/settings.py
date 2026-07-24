from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.settings_service import (
    get_settings,
    update_settings,
)

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")


@router.get("/settings")
def settings_page(
    request: Request,
    saved: bool = False,
    db: Session = Depends(get_db),
):
    settings = get_settings(db)

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "settings": settings,
            "saved": saved,
        },
    )

@router.post("/settings")
def save_settings(
    bankroll: float = Form(...),
    default_stake_percent: float = Form(...),
    kelly_fraction: float = Form(...),
    max_daily_risk: float = Form(...),
    minimum_edge: float = Form(...),
    minimum_confidence: float = Form(...),
    auto_refresh: bool = Form(False),
    refresh_interval: int = Form(...),
    db: Session = Depends(get_db),
):
    update_settings(
        db,
        bankroll=bankroll,
        default_stake_percent=default_stake_percent,
        kelly_fraction=kelly_fraction,
        max_daily_risk=max_daily_risk,
        minimum_edge=minimum_edge,
        minimum_confidence=minimum_confidence,
        auto_refresh=auto_refresh,
        refresh_interval=refresh_interval,
    )

    return RedirectResponse(
        "/settings?saved=1",
        status_code=303,
    )