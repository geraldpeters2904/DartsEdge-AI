from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.strategy_service import activate_strategy, get_active_strategy, list_strategies, strategy_summary
from app.templates_config import templates

router = APIRouter()


@router.get("/strategies")
def strategies_page(request: Request, db: Session = Depends(get_db)):
    strategies = list(list_strategies(db))
    active = get_active_strategy(db)
    return templates.TemplateResponse(
        "strategies.html",
        {
            "request": request,
            "strategies": [strategy_summary(item) for item in strategies],
            "active_strategy": strategy_summary(active),
        },
    )


@router.post("/strategies/activate")
def activate_strategy_route(strategy_id: int = Form(...), db: Session = Depends(get_db)):
    try:
        activate_strategy(db, strategy_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/strategies", status_code=303)


@router.get("/api/strategies")
def strategies_api(db: Session = Depends(get_db)):
    strategies = [strategy_summary(item) for item in list_strategies(db)]
    active = get_active_strategy(db)
    return {"registered": len(strategies), "active": strategy_summary(active), "strategies": strategies}
