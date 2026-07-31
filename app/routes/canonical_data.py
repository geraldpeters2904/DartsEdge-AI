from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.canonical_data_service import summary
router=APIRouter(); templates=Jinja2Templates(directory='app/templates')
@router.get('/data-warehouse')
def page(request: Request, db: Session=Depends(get_db)):
    return templates.TemplateResponse(request,'data_warehouse.html',{'summary':summary(db)})
@router.get('/api/data-warehouse')
def api(db: Session=Depends(get_db)):
    return summary(db)
