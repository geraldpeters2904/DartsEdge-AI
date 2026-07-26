import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.strategy_service import (
    activate_strategy,
    create_strategy,
    duplicate_strategy,
    export_strategy,
    get_active_strategy,
    get_strategy,
    import_strategy,
    list_strategies,
    strategy_history,
    strategy_rules,
    strategy_summary,
    update_strategy,
)
from app.templates_config import templates

router = APIRouter()


def _latest_rows(strategies):
    latest = {}
    for strategy in strategies:
        current = latest.get(strategy.strategy_uuid)
        if current is None or strategy.version > current.version:
            latest[strategy.strategy_uuid] = strategy
    return sorted(latest.values(), key=lambda item: item.name.lower())


def _form_rules(form) -> dict:
    def number(name, default):
        value = form.get(name)
        return default if value in (None, "") else float(value)

    def string_list(name):
        value = str(form.get(name, ""))
        return [item.strip().lower() for item in value.split(",") if item.strip()]

    return {
        "mode": str(form.get("mode", "live")),
        "decision_rules_enabled": form.get("decision_rules_enabled") == "on",
        "enforcement_mode": str(form.get("enforcement_mode", "shadow")),
        "minimum_ev_percent": number("minimum_ev_percent", 0),
        "minimum_edge_percent": number("minimum_edge_percent", 0),
        "minimum_model_probability": number("minimum_model_probability", 0),
        "minimum_confidence_percent": number("minimum_confidence_percent", 0),
        "kelly_fraction": number("kelly_fraction", 0.5),
        "maximum_portfolio_exposure_percent": number("maximum_portfolio_exposure_percent", 15),
        "maximum_stake_percent": number("maximum_stake_percent", 3),
        "minimum_sample_size": int(number("minimum_sample_size", 0)),
        "maximum_decimal_odds": number("maximum_decimal_odds", 10),
        "allowed_markets": string_list("allowed_markets"),
        "allowed_competitions": string_list("allowed_competitions"),
    }


@router.get("/strategies")
def strategies_page(request: Request, db: Session = Depends(get_db)):
    strategies = _latest_rows(list(list_strategies(db)))
    active = get_active_strategy(db)
    return templates.TemplateResponse(
        "strategies.html",
        {
            "request": request,
            "strategies": [strategy_summary(item) for item in strategies],
            "active_strategy": strategy_summary(active),
        },
    )


@router.get("/strategy-editor")
def strategy_editor_page(request: Request, strategy_id: int = 0, db: Session = Depends(get_db)):
    strategy = get_strategy(db, strategy_id) if strategy_id else None
    return templates.TemplateResponse(
        "strategy_editor.html",
        {
            "request": request,
            "strategy": strategy_summary(strategy) if strategy else None,
            "history": [strategy_summary(item) for item in strategy_history(db, strategy.strategy_uuid)] if strategy else [],
            "error": None,
        },
    )


@router.post("/strategy-editor/save")
async def save_strategy_route(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    strategy_id = int(form.get("strategy_id") or 0)
    try:
        rules = _form_rules(form)
        if strategy_id:
            saved = update_strategy(
                db,
                strategy_id,
                name=str(form.get("name", "")),
                description=str(form.get("description", "")),
                rules=rules,
            )
        else:
            saved = create_strategy(
                db,
                name=str(form.get("name", "")),
                description=str(form.get("description", "")),
                rules=rules,
            )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/strategy-editor?strategy_id={saved.id}", status_code=303)


@router.post("/strategies/activate")
def activate_strategy_route(strategy_id: int = Form(...), db: Session = Depends(get_db)):
    try:
        activate_strategy(db, strategy_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/strategies", status_code=303)


@router.post("/strategies/duplicate")
def duplicate_strategy_route(strategy_id: int = Form(...), db: Session = Depends(get_db)):
    try:
        duplicate = duplicate_strategy(db, strategy_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/strategy-editor?strategy_id={duplicate.id}", status_code=303)


@router.get("/strategies/{strategy_id}/export")
def export_strategy_route(strategy_id: int, db: Session = Depends(get_db)):
    try:
        strategy = get_strategy(db, strategy_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    filename = strategy.name.lower().replace(" ", "-") + f"-v{strategy.version}.json"
    return JSONResponse(
        export_strategy(strategy),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/strategies/import")
def import_strategy_route(payload_json: str = Form(...), db: Session = Depends(get_db)):
    try:
        payload = json.loads(payload_json)
        imported = import_strategy(db, payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=f"/strategy-editor?strategy_id={imported.id}", status_code=303)


@router.get("/api/strategies")
def strategies_api(db: Session = Depends(get_db)):
    strategies = [strategy_summary(item) for item in _latest_rows(list(list_strategies(db)))]
    active = get_active_strategy(db)
    return {"registered": len(strategies), "active": strategy_summary(active), "strategies": strategies}
