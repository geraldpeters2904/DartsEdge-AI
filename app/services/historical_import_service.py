import csv, io, json, re, uuid, zipfile
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.player import Player
from app.models.match import Match
from app.models.match_player_stats import MatchPlayerStats
from app.models.odds_snapshot import OddsSnapshot
from app.models.player_match_performance import PlayerMatchPerformance
from app.models.historical_import import HistoricalImportBatch, HistoricalImportItem, PlayerAlias
from app.services.canonical_data_service import store_raw, map_entity, record_provenance, SUPPORTED_COMPETITIONS

REQUIRED = ('date','player_a','player_b')
STAT_FIELDS = ('average','checkout','first9','highest_checkout','180s')

def _name_key(value):
    value = (value or '').strip().lower()
    return re.sub(r'[^a-z0-9]+','',value)

def _number(value, cast=float, default=0):
    if value in (None,''): return default
    try: return cast(float(value))
    except (TypeError, ValueError): return default

def _normalise_row(row, provider, default_competition):
    r = {str(k).strip().lower(): v for k,v in row.items() if k is not None}
    missing=[k for k in REQUIRED if not str(r.get(k,'')).strip()]
    if missing: raise ValueError('Missing required field(s): '+', '.join(missing))
    try: match_date=datetime.strptime(str(r['date'])[:10],'%Y-%m-%d').date()
    except ValueError: raise ValueError('date must use YYYY-MM-DD')
    competition=str(r.get('competition') or r.get('tournament') or default_competition).strip().upper()
    if competition not in SUPPORTED_COMPETITIONS: competition='OTHER'
    external_id=str(r.get('external_id') or f"{competition}:{match_date}:{_name_key(r['player_a'])}:{_name_key(r['player_b'])}")
    out={
      'external_id':external_id,'date':match_date,'competition':competition,
      'tournament':str(r.get('tournament') or competition).strip(),
      'stage':str(r.get('stage') or 'Historical').strip(),
      'match_format':str(r.get('match_format') or r.get('format') or 'Best of 7').strip(),
      'status':str(r.get('status') or ('completed' if r.get('winner') else 'scheduled')).strip().lower(),
      'player_a':str(r['player_a']).strip(),'player_b':str(r['player_b']).strip(),
      'winner':str(r.get('winner') or '').strip() or None,'score':str(r.get('score') or '').strip() or None,
      'first_180_player':str(r.get('first_180_player') or '').strip() or None,
      'first_leg_winner':str(r.get('first_leg_winner') or '').strip() or None,
      'provider':provider,
    }
    for side in ('player_a','player_b'):
      out[side+'_stats']={
        'one80s':_number(r.get(side+'_180s'),int,0),
        'average':_number(r.get(side+'_average'),float,0),
        'checkout':_number(r.get(side+'_checkout'),float,0),
        'first9_average':_number(r.get(side+'_first9'),float,0),
        'highest_checkout':_number(r.get(side+'_highest_checkout'),int,0),
      }
    return out

def parse_upload(filename, content, provider='historical-upload', competition='MODUS'):
    suffix=Path(filename).suffix.lower(); rows=[]
    if suffix=='.csv':
      rows=list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))
    elif suffix=='.json':
      data=json.loads(content.decode('utf-8-sig')); rows=data.get('matches',data) if isinstance(data,dict) else data
      if not isinstance(rows,list): raise ValueError('JSON must be a list or contain a matches list')
    elif suffix=='.zip':
      with zipfile.ZipFile(io.BytesIO(content)) as z:
        for name in z.namelist():
          if name.lower().endswith(('.csv','.json')) and not name.startswith('__MACOSX/'):
            rows.extend(parse_upload(name,z.read(name),provider,competition))
      return rows
    else: raise ValueError('Supported formats are CSV, JSON and ZIP')
    return [_normalise_row(row,provider,competition) for row in rows]

def preview_rows(rows):
    players=set(); errors=[]; valid=[]
    for i,row in enumerate(rows,1):
      try:
        if not isinstance(row,dict) or 'date' not in row: raise ValueError('Invalid row')
        valid.append(row); players.update((row['player_a'],row['player_b']))
      except Exception as exc: errors.append({'row':i,'error':str(exc)})
    return {'received':len(rows),'valid':len(valid),'rejected':len(errors),'players':len(players),'competitions':sorted({r['competition'] for r in valid}),'errors':errors[:20]}

def _resolve_player(db,name,provider,batch):
    key=_name_key(name)
    alias=db.query(PlayerAlias).filter_by(provider=provider,alias_key=key).first()
    if alias:
      player=db.query(Player).filter(Player.id==alias.player_id).first()
      if player: return player,False
    player=db.query(Player).filter(Player.name==name).first()
    if not player:
      player=Player(name=name,elo=1500.0,average=0.0,checkout=0.0,one80_rate=0.0); db.add(player); db.flush()
      db.add(HistoricalImportItem(batch_id=batch.id,entity_type='player',internal_id=player.id,external_id=name,action='created',created_by_batch=True))
      created=True
    else: created=False
    if not alias:
      db.add(PlayerAlias(provider=provider,alias=name,alias_key=key,player_id=player.id))
    map_entity(db,provider,'player',name,player.id)
    return player,created

def import_rows(db,rows,filename,provider='historical-upload',competition='MODUS'):
    batch=HistoricalImportBatch(batch_uuid=str(uuid.uuid4()),filename=filename,provider=provider,competition_code=competition,received_rows=len(rows),status='importing')
    db.add(batch); db.flush(); created_players=created_matches=duplicates=rejected=0
    try:
      for row in rows:
        try:
          raw,_=store_raw(db,provider,'fixture',row['external_id'],{**row,'date':row['date'].isoformat()})
          pa,ca=_resolve_player(db,row['player_a'],provider,batch); pb,cb=_resolve_player(db,row['player_b'],provider,batch)
          created_players += int(ca)+int(cb)
          existing=db.query(Match).filter(Match.date==row['date'],Match.player_a==row['player_a'],Match.player_b==row['player_b'],Match.tournament==row['tournament']).first()
          if existing:
            duplicates+=1; db.add(HistoricalImportItem(batch_id=batch.id,entity_type='match',internal_id=existing.id,external_id=row['external_id'],action='duplicate',created_by_batch=False)); continue
          match=Match(date=row['date'],tournament=row['tournament'],stage=row['stage'],match_format=row['match_format'],status=row['status'],player_a=row['player_a'],player_b=row['player_b'],winner=row['winner'],score=row['score'],first_180_player=row['first_180_player'],first_leg_winner=row['first_leg_winner'])
          db.add(match); db.flush(); created_matches+=1
          for side in ('player_a','player_b'):
            stats=row[side+'_stats']; db.add(MatchPlayerStats(match_id=match.id,player_name=row[side],**stats))
          db.add(HistoricalImportItem(batch_id=batch.id,entity_type='match',internal_id=match.id,external_id=row['external_id'],action='created',created_by_batch=True))
          map_entity(db,provider,'fixture',row['external_id'],match.id,row['competition'])
          for field in ('date','tournament','stage','status','winner','score'):
            record_provenance(db,'fixture',match.id,field,provider,row['external_id'])
          raw.processed=True
        except Exception as exc:
          rejected+=1; db.add(HistoricalImportItem(batch_id=batch.id,entity_type='row',external_id=row.get('external_id'),action='rejected',detail=str(exc),created_by_batch=False))
      batch.created_players=created_players; batch.created_matches=created_matches; batch.duplicate_matches=duplicates; batch.rejected_rows=rejected; batch.status='imported'; db.commit(); db.refresh(batch); return batch
    except Exception as exc:
      db.rollback(); raise

def rollback_batch(db,batch_id):
    batch=db.query(HistoricalImportBatch).filter_by(id=batch_id).first()
    if not batch: raise ValueError('Import batch not found')
    if batch.status=='rolled_back': return batch
    items=db.query(HistoricalImportItem).filter_by(batch_id=batch.id,created_by_batch=True).order_by(HistoricalImportItem.id.desc()).all()
    odds_ids=[i.internal_id for i in items if i.entity_type=='odds_snapshot' and i.internal_id]
    performance_ids=[i.internal_id for i in items if i.entity_type=='player_match_performance' and i.internal_id]
    match_ids=[i.internal_id for i in items if i.entity_type=='match' and i.internal_id]
    player_ids=[i.internal_id for i in items if i.entity_type=='player' and i.internal_id]
    if odds_ids:
      db.query(OddsSnapshot).filter(OddsSnapshot.id.in_(odds_ids)).delete(synchronize_session=False)
    if performance_ids:
      db.query(PlayerMatchPerformance).filter(PlayerMatchPerformance.id.in_(performance_ids)).delete(synchronize_session=False)
    if match_ids:
      db.query(MatchPlayerStats).filter(MatchPlayerStats.match_id.in_(match_ids)).delete(synchronize_session=False)
      db.query(Match).filter(Match.id.in_(match_ids)).delete(synchronize_session=False)
    for pid in player_ids:
      used=db.query(Match).filter((Match.player_a==db.query(Player.name).filter(Player.id==pid).scalar_subquery()) | (Match.player_b==db.query(Player.name).filter(Player.id==pid).scalar_subquery())).first()
      if not used:
        db.query(PlayerAlias).filter_by(player_id=pid).delete(synchronize_session=False); db.query(Player).filter_by(id=pid).delete(synchronize_session=False)
    batch.status='rolled_back'; batch.rolled_back_at=datetime.utcnow(); db.commit(); db.refresh(batch); return batch

def batches(db,limit=25):
    return db.query(HistoricalImportBatch).order_by(HistoricalImportBatch.id.desc()).limit(limit).all()

# --- Pack 3: staged preview and player reconciliation ---
from difflib import SequenceMatcher
from app.models.historical_import import HistoricalImportPreview

def _json_safe_row(row):
    result = dict(row)
    if hasattr(result.get('date'), 'isoformat'):
        result['date'] = result['date'].isoformat()
    return result

def _restore_row(row):
    result = dict(row)
    if isinstance(result.get('date'), str):
        result['date'] = datetime.strptime(result['date'][:10], '%Y-%m-%d').date()
    return result

def create_import_preview(db, filename, content, provider='historical-upload', competition='MODUS'):
    rows = parse_upload(filename, content, provider, competition)
    report = preview_rows(rows)
    preview = HistoricalImportPreview(
        preview_uuid=str(uuid.uuid4()), filename=filename, provider=provider,
        competition_code=competition, status='pending',
        rows_json=json.dumps([_json_safe_row(r) for r in rows], separators=(',', ':')),
        report_json=json.dumps(report, separators=(',', ':')),
    )
    db.add(preview); db.commit(); db.refresh(preview)
    return preview

def get_import_preview(db, preview_uuid):
    return db.query(HistoricalImportPreview).filter_by(preview_uuid=preview_uuid).first()

def preview_rows_from_record(preview):
    return [_restore_row(r) for r in json.loads(preview.rows_json)]

def _candidate_score(alias_key, player_name):
    return SequenceMatcher(None, alias_key, _name_key(player_name)).ratio()

def player_reconciliation(db, preview):
    rows = preview_rows_from_record(preview)
    names = sorted({r['player_a'] for r in rows} | {r['player_b'] for r in rows})
    players = db.query(Player).order_by(Player.name).all()
    result = []
    for name in names:
        key = _name_key(name)
        alias = db.query(PlayerAlias).filter_by(provider=preview.provider, alias_key=key).first()
        exact = db.query(Player).filter(Player.name == name).first()
        mapped = None
        status = 'unresolved'
        if alias:
            mapped = db.query(Player).filter(Player.id == alias.player_id).first()
            status = 'alias'
        elif exact:
            mapped = exact
            status = 'exact'
        candidates = sorted(
            ({'id': p.id, 'name': p.name, 'score': round(_candidate_score(key, p.name), 3)} for p in players),
            key=lambda x: x['score'], reverse=True,
        )[:5]
        candidates = [c for c in candidates if c['score'] >= 0.55]
        result.append({'source_name': name, 'status': status, 'mapped': mapped, 'candidates': candidates})
    return result

def _resolve_player_with_overrides(db, name, provider, batch, overrides=None):
    overrides = overrides or {}
    choice = overrides.get(name)
    if choice not in (None, '', 'new'):
        try: player_id = int(choice)
        except (TypeError, ValueError): player_id = 0
        player = db.query(Player).filter(Player.id == player_id).first()
        if not player: raise ValueError(f'Chosen player mapping does not exist for {name}')
        key = _name_key(name)
        alias = db.query(PlayerAlias).filter_by(provider=provider, alias_key=key).first()
        if alias and alias.player_id != player.id:
            alias.player_id = player.id
        elif not alias:
            db.add(PlayerAlias(provider=provider, alias=name, alias_key=key, player_id=player.id))
        map_entity(db, provider, 'player', name, player.id)
        return player, False
    return _resolve_player(db, name, provider, batch)

def import_rows_with_mappings(db, rows, filename, provider='historical-upload', competition='MODUS', player_mappings=None):
    # Same canonical import contract as import_rows, with explicit player decisions.
    batch=HistoricalImportBatch(batch_uuid=str(uuid.uuid4()),filename=filename,provider=provider,competition_code=competition,received_rows=len(rows),status='importing')
    db.add(batch); db.flush(); created_players=created_matches=duplicates=rejected=0
    try:
      for row in rows:
        try:
          raw,_=store_raw(db,provider,'fixture',row['external_id'],{**row,'date':row['date'].isoformat()})
          pa,ca=_resolve_player_with_overrides(db,row['player_a'],provider,batch,player_mappings)
          pb,cb=_resolve_player_with_overrides(db,row['player_b'],provider,batch,player_mappings)
          created_players += int(ca)+int(cb)
          # Store canonical player names when an alias was explicitly reconciled.
          player_a_name, player_b_name = pa.name, pb.name
          existing=db.query(Match).filter(Match.date==row['date'],Match.player_a==player_a_name,Match.player_b==player_b_name,Match.tournament==row['tournament']).first()
          if existing:
            duplicates+=1; db.add(HistoricalImportItem(batch_id=batch.id,entity_type='match',internal_id=existing.id,external_id=row['external_id'],action='duplicate',created_by_batch=False)); continue
          match=Match(date=row['date'],tournament=row['tournament'],stage=row['stage'],match_format=row['match_format'],status=row['status'],player_a=player_a_name,player_b=player_b_name,winner=(pa.name if row['winner']==row['player_a'] else pb.name if row['winner']==row['player_b'] else row['winner']),score=row['score'],first_180_player=row['first_180_player'],first_leg_winner=row['first_leg_winner'])
          db.add(match); db.flush(); created_matches+=1
          for side, canonical_name in (('player_a', player_a_name), ('player_b', player_b_name)):
            stats=row[side+'_stats']; db.add(MatchPlayerStats(match_id=match.id,player_name=canonical_name,**stats))
          db.add(HistoricalImportItem(batch_id=batch.id,entity_type='match',internal_id=match.id,external_id=row['external_id'],action='created',created_by_batch=True))
          map_entity(db,provider,'fixture',row['external_id'],match.id,row['competition'])
          for field in ('date','tournament','stage','status','winner','score'):
            record_provenance(db,'fixture',match.id,field,provider,row['external_id'])
          raw.processed=True
        except Exception as exc:
          rejected+=1; db.add(HistoricalImportItem(batch_id=batch.id,entity_type='row',external_id=row.get('external_id'),action='rejected',detail=str(exc),created_by_batch=False))
      batch.created_players=created_players; batch.created_matches=created_matches; batch.duplicate_matches=duplicates; batch.rejected_rows=rejected; batch.status='imported'; db.commit(); db.refresh(batch); return batch
    except Exception:
      db.rollback(); raise

def commit_import_preview(db, preview_uuid, player_mappings=None):
    preview = get_import_preview(db, preview_uuid)
    if not preview: raise ValueError('Import preview not found')
    if preview.status == 'committed':
        return db.query(HistoricalImportBatch).filter_by(id=preview.batch_id).first()
    if preview.status != 'pending': raise ValueError('Import preview is no longer pending')
    batch = import_rows_with_mappings(db, preview_rows_from_record(preview), preview.filename, preview.provider, preview.competition_code, player_mappings)
    preview.status='committed'; preview.batch_id=batch.id; preview.committed_at=datetime.utcnow(); db.commit(); db.refresh(preview)
    return batch

def cancel_import_preview(db, preview_uuid):
    preview = get_import_preview(db, preview_uuid)
    if not preview: raise ValueError('Import preview not found')
    if preview.status == 'pending': preview.status='cancelled'; db.commit(); db.refresh(preview)
    return preview
