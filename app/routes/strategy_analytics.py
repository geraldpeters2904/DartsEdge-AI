from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.strategy_analytics_service import analytics, settle_decision
from app.templates_config import templates

router = APIRouter()


@router.get('/strategy-analytics')
def strategy_analytics_page(request: Request, window: str = 'all', db: Session = Depends(get_db)):
    days = {'7': 7, '30': 30}.get(window)
    report = analytics(db, days=days)
    return templates.TemplateResponse('strategy_analytics.html', {'request': request, 'report': report, 'window': window})


@router.post('/strategy-analytics/settle')
def settle_strategy_decision(decision_id: int = Form(...), outcome: str = Form(...), db: Session = Depends(get_db)):
    settle_decision(db, decision_id, outcome)
    return RedirectResponse('/strategy-analytics', status_code=303)


@router.get('/api/strategy-analytics')
def strategy_analytics_api(window: str = 'all', db: Session = Depends(get_db)):
    days = {'7': 7, '30': 30}.get(window)
    report = analytics(db, days=days)
    return {
        'active_strategy': report['active_strategy'],
        'total_decisions': report['total_decisions'],
        'settled_decisions': report['settled_decisions'],
        'insufficient_data': report['insufficient_data'],
        'metrics': [metric.__dict__ for metric in report['metrics']],
        'rejection_reasons': report['rejection_reasons'],
        'competitions': report['competitions'],
    }
