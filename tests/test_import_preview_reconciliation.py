import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models.player import Player
from app.models.match import Match
from app.models.historical_import import HistoricalImportPreview, PlayerAlias
from app.services.historical_import_service import create_import_preview, player_reconciliation, commit_import_preview, cancel_import_preview

class ImportPreviewReconciliationTests(unittest.TestCase):
 def setUp(self):
  engine=create_engine('sqlite:///:memory:'); Base.metadata.create_all(engine); self.db=sessionmaker(bind=engine)()
 def tearDown(self): self.db.close()
 def sample(self,name='M. Smith'):
  return f'date,external_id,tournament,player_a,player_b\n2026-02-01,p1,MODUS,{name},Other Player\n'.encode()
 def test_preview_does_not_import_matches(self):
  p=create_import_preview(self.db,'x.csv',self.sample()); self.assertEqual(p.status,'pending'); self.assertEqual(self.db.query(Match).count(),0)
 def test_close_candidate_is_reported(self):
  self.db.add(Player(name='Michael Smith',elo=1500,average=0,checkout=0,one80_rate=0)); self.db.commit()
  p=create_import_preview(self.db,'x.csv',self.sample()); rows=player_reconciliation(self.db,p); item=next(x for x in rows if x['source_name']=='M. Smith'); self.assertTrue(any(c['name']=='Michael Smith' for c in item['candidates']))
 def test_commit_maps_alias_to_existing_player(self):
  player=Player(name='Michael Smith',elo=1500,average=0,checkout=0,one80_rate=0); self.db.add(player); self.db.commit()
  p=create_import_preview(self.db,'x.csv',self.sample()); batch=commit_import_preview(self.db,p.preview_uuid,{'M. Smith':str(player.id),'Other Player':'new'})
  self.assertEqual(batch.created_matches,1); match=self.db.query(Match).one(); self.assertEqual(match.player_a,'Michael Smith'); self.assertEqual(self.db.query(PlayerAlias).filter_by(alias_key='msmith').one().player_id,player.id)
 def test_committing_twice_is_idempotent(self):
  p=create_import_preview(self.db,'x.csv',self.sample('New One')); b1=commit_import_preview(self.db,p.preview_uuid,{}); b2=commit_import_preview(self.db,p.preview_uuid,{}); self.assertEqual(b1.id,b2.id); self.assertEqual(self.db.query(Match).count(),1)
 def test_cancel_keeps_database_unchanged(self):
  p=create_import_preview(self.db,'x.csv',self.sample()); cancel_import_preview(self.db,p.preview_uuid); self.assertEqual(self.db.query(HistoricalImportPreview).one().status,'cancelled'); self.assertEqual(self.db.query(Match).count(),0)
if __name__=='__main__': unittest.main()
