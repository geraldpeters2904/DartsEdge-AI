from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.db import SessionLocal
from app.models.player import Player
from app.services.expected_value_service import assess_value, best_prices, recent_snapshots, store_snapshot
from app.services.decision_engine_service import decide
from app.services.portfolio_health_service import build_portfolio_health
from app.services.settings_service import get_settings
from app.services.strategy_service import evaluate_strategy, get_active_strategy, strategy_summary
from app.templates_config import templates

router = APIRouter()


def _page_context(db, request: Request, *, assessment=None, strategy_decision=None, decision_engine=None, error=None, message=None):
    settings = get_settings(db)
    active_strategy = get_active_strategy(db)
    snapshots = recent_snapshots(db)
    return {
        "request": request,
        "assessment": assessment,
        "strategy_decision": strategy_decision,
        "decision_engine": decision_engine,
        "active_strategy": strategy_summary(active_strategy),
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
    confidence_percent: float = Form(100.0),
    sample_size: int = Form(0),
    market: str = Form("match_winner"),
    competition: str = Form(""),
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
        active_strategy = get_active_strategy(db)
        portfolio = build_portfolio_health(db)
        strategy_decision = evaluate_strategy(
            active_strategy,
            model_probability=assessment.model_probability,
            confidence_percent=confidence_percent,
            expected_value_percent=assessment.expected_value_percent,
            edge_percent=assessment.edge_percent,
            decimal_odds=assessment.decimal_odds,
            bankroll=settings.bankroll,
            raw_kelly_stake=assessment.recommended_stake,
            market=market,
            competition=competition,
            sample_size=sample_size,
            portfolio_exposure_percent=portfolio.get("exposure_percent"),
        )
        decision_engine = decide(
            db, official_decision=assessment.decision, official_stake=assessment.recommended_stake,
            model_probability=assessment.model_probability, confidence_percent=confidence_percent,
            expected_value_percent=assessment.expected_value_percent, edge_percent=assessment.edge_percent,
            decimal_odds=assessment.decimal_odds, bankroll=settings.bankroll, market=market,
            competition=competition, sample_size=sample_size,
            portfolio_exposure_percent=portfolio.get("exposure_percent"),
        )
        return templates.TemplateResponse(
            "expected_value.html",
            _page_context(db, request, assessment=assessment, strategy_decision=strategy_decision, decision_engine=decision_engine),
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
