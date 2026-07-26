from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.db import SessionLocal
from app.models.player import Player
from app.services.expected_value_service import assess_value, best_prices, recent_snapshots, store_snapshot
from app.services.settings_service import get_settings
from app.templates_config import templates

router = APIRouter()


def _page_context(db, request: Request, *, assessment=None, error=None, message=None):
    settings = get_settings(db)
    snapshots = recent_snapshots(db)
    return {
        "request": request,
        "assessment": assessment,
        "error": error,
        "message": message,
        "snapshots": snapshots,
        "best_prices": best_prices(snapshots),
        "players": db.query(Player).order_by(Player.name.asc()).all(),
        "settings": settings,
        "today": date.today().isoformat(),
    }


@router.get("/expected-value")
def expected_value_page(request: Request):
    db = SessionLocal()
    try:
        return templates.TemplateResponse("expected_value.html", _page_context(db, request))
    finally:
        db.close()


@router.post("/expected-value")
def calculate_expected_value(
    request: Request,
    model_probability: float = Form(...),
    decimal_odds: float = Form(...),
    bookmaker: str = Form(...),
):
    db = SessionLocal()
    try:
        settings = get_settings(db)
        assessment = assess_value(
            model_probability=model_probability,
            decimal_odds=decimal_odds,
            bookmaker=bookmaker,
            bankroll=settings.bankroll,
            kelly_fraction=settings.kelly_fraction,
            max_daily_risk_percent=settings.max_daily_risk,
            minimum_edge_percent=settings.minimum_edge,
        )
        return templates.TemplateResponse(
            "expected_value.html", _page_context(db, request, assessment=assessment)
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            "expected_value.html", _page_context(db, request, error=str(exc)), status_code=400
        )
    finally:
        db.close()


@router.post("/odds-snapshots")
def add_odds_snapshot(
    fixture_date: date = Form(...),
    tournament: str = Form("Unknown"),
    player_a: str = Form(...),
    player_b: str = Form(...),
    market: str = Form("match_winner"),
    selection: str = Form(...),
    bookmaker: str = Form(...),
    decimal_odds: float = Form(...),
    captured_at: Optional[str] = Form(None),
):
    db = SessionLocal()
    try:
        captured = datetime.fromisoformat(captured_at) if captured_at else None
        _, created = store_snapshot(
            db,
            fixture_date=fixture_date,
            tournament=tournament,
            player_a=player_a,
            player_b=player_b,
            market=market,
            selection=selection,
            bookmaker=bookmaker,
            decimal_odds=decimal_odds,
            captured_at=captured,
        )
        status = "created" if created else "duplicate"
        return RedirectResponse(url=f"/expected-value?status={status}", status_code=303)
    except ValueError as exc:
        return RedirectResponse(url=f"/expected-value?error={str(exc)}", status_code=303)
    finally:
        db.close()
