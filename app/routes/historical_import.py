import json
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.player import Player
from app.services.historical_import_service import (
    create_import_preview, get_import_preview, player_reconciliation,
    commit_import_preview, cancel_import_preview, rollback_batch, batches,
)
router=APIRouter(); templates=Jinja2Templates(directory='app/templates')

def _redirect(path, message):
    from urllib.parse import quote
    return RedirectResponse(f'{path}?message={quote(message)}', status_code=303)

@router.get('/admin/imports')
def page(request:Request,db:Session=Depends(get_db)):
    return templates.TemplateResponse(request,'historical_import.html',{'batches':batches(db),'message':request.query_params.get('message')})

@router.post('/admin/imports/upload')
async def upload(file:UploadFile=File(...),provider:str=Form('historical-upload'),competition:str=Form('MODUS'),db:Session=Depends(get_db)):
    try:
      content=await file.read(); preview=create_import_preview(db,file.filename or 'upload.csv',content,provider,competition)
      return RedirectResponse(f'/admin/imports/preview/{preview.preview_uuid}',status_code=303)
    except Exception as exc:
      return _redirect('/admin/imports','Preview failed: '+str(exc))

@router.get('/admin/imports/preview/{preview_uuid}')
def preview_page(preview_uuid:str,request:Request,db:Session=Depends(get_db)):
    preview=get_import_preview(db,preview_uuid)
    if not preview: return _redirect('/admin/imports','Import preview not found.')
    return templates.TemplateResponse(request,'historical_import_preview.html',{
      'preview':preview,'report':json.loads(preview.report_json),
      'reconciliation':player_reconciliation(db,preview),
      'players':db.query(Player).order_by(Player.name).all(),
      'message':request.query_params.get('message'),
    })

@router.post('/admin/imports/preview/{preview_uuid}/commit')
async def commit(preview_uuid:str,request:Request,db:Session=Depends(get_db)):
    try:
      form=await request.form(); mappings={}
      count=int(form.get('player_count','0'))
      for index in range(count):
        name=str(form.get(f'player_name_{index}',''))
        choice=str(form.get(f'player_choice_{index}','new'))
        if name: mappings[name]=choice
      batch=commit_import_preview(db,preview_uuid,mappings)
      return _redirect('/admin/imports',f'Batch {batch.batch_uuid[:8]} imported: {batch.created_matches} matches, {batch.created_players} players, {batch.duplicate_matches} duplicates, {batch.rejected_rows} rejected.')
    except Exception as exc:
      return _redirect(f'/admin/imports/preview/{preview_uuid}','Import failed: '+str(exc))

@router.post('/admin/imports/preview/{preview_uuid}/cancel')
def cancel(preview_uuid:str,db:Session=Depends(get_db)):
    cancel_import_preview(db,preview_uuid)
    return _redirect('/admin/imports','Import preview cancelled. No match data was changed.')

@router.post('/admin/imports/{batch_id}/rollback')
def rollback(batch_id:int,db:Session=Depends(get_db)):
    batch=rollback_batch(db,batch_id)
    return _redirect('/admin/imports',f'Batch {batch.batch_uuid[:8]} rolled back.')

@router.get('/api/imports')
def api(db:Session=Depends(get_db)):
    return {'batches':[{'id':b.id,'uuid':b.batch_uuid,'filename':b.filename,'provider':b.provider,'competition':b.competition_code,'status':b.status,'received':b.received_rows,'created_matches':b.created_matches,'duplicates':b.duplicate_matches,'rejected':b.rejected_rows} for b in batches(db)]}
