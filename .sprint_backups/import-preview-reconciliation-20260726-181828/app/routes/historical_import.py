from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import get_db
from app.services.historical_import_service import parse_upload, preview_rows, import_rows, rollback_batch, batches
router=APIRouter(); templates=Jinja2Templates(directory='app/templates')

@router.get('/admin/imports')
def page(request:Request,db:Session=Depends(get_db)):
    return templates.TemplateResponse(request,'historical_import.html',{'batches':batches(db),'message':request.query_params.get('message')})

@router.post('/admin/imports/upload')
async def upload(file:UploadFile=File(...),provider:str=Form('historical-upload'),competition:str=Form('MODUS'),db:Session=Depends(get_db)):
    try:
      content=await file.read(); rows=parse_upload(file.filename or 'upload.csv',content,provider,competition); report=preview_rows(rows)
      batch=import_rows(db,rows,file.filename or 'upload',provider,competition)
      msg=f"Batch {batch.batch_uuid[:8]} imported: {batch.created_matches} matches, {batch.created_players} players, {batch.duplicate_matches} duplicates, {batch.rejected_rows} rejected."
    except Exception as exc: msg='Import failed: '+str(exc)
    return RedirectResponse('/admin/imports?message='+msg.replace(' ','%20'),status_code=303)

@router.post('/admin/imports/{batch_id}/rollback')
def rollback(batch_id:int,db:Session=Depends(get_db)):
    batch=rollback_batch(db,batch_id)
    return RedirectResponse(f'/admin/imports?message=Batch%20{batch.batch_uuid[:8]}%20rolled%20back.',status_code=303)

@router.get('/api/imports')
def api(db:Session=Depends(get_db)):
    return {'batches':[{'id':b.id,'uuid':b.batch_uuid,'filename':b.filename,'provider':b.provider,'competition':b.competition_code,'status':b.status,'received':b.received_rows,'created_matches':b.created_matches,'duplicates':b.duplicate_matches,'rejected':b.rejected_rows} for b in batches(db)]}
