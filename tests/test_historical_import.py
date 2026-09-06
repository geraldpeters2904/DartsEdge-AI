from datetime import date
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models.player import Player
from app.models.match import Match
from app.models.match_player_stats import MatchPlayerStats
from app.models.canonical_data import RawIngestionRecord, ProviderEntityMapping, DataProvenance
from app.models.historical_import import HistoricalImportBatch, HistoricalImportItem, PlayerAlias
from app.services.historical_import_service import parse_upload, preview_rows, import_rows, rollback_batch

class HistoricalImportTests(unittest.TestCase):
 def setUp(self):
  engine=create_engine('sqlite:///:memory:'); Base.metadata.create_all(engine); self.db=sessionmaker(bind=engine)()
 def tearDown(self): self.db.close()
 def sample(self):
  return b'date,external_id,tournament,player_a,player_b,winner,score,player_a_average,player_b_average\n2026-01-02,m1,MODUS,A One,B Two,A One,4-2,92.1,88.4\n'
 def test_csv_parse_and_preview(self):
  rows=parse_upload('x.csv',self.sample()); report=preview_rows(rows); self.assertEqual(report['valid'],1); self.assertEqual(rows[0]['competition'],'MODUS')
 def test_parse_canonicalises_player_display_names(self):
  content = (
   b'date,external_id,tournament,player_a,player_b,winner\n'
   b'2026-01-02,m2,MODUS,Noa-Lynn van_Leuven_,B Two,Noa-Lynn van_Leuven_\n'
  )
  row = parse_upload('x.csv', content)[0]
  self.assertEqual(row['player_a'], 'Noa-Lynn van Leuven')
  self.assertEqual(row['winner'], 'Noa-Lynn van Leuven')

 def test_import_creates_canonical_and_app_records(self):
  batch=import_rows(self.db,parse_upload('x.csv',self.sample()),'x.csv'); self.assertEqual(batch.created_matches,1); self.assertEqual(self.db.query(Match).count(),1); self.assertEqual(self.db.query(Player).count(),2); self.assertEqual(self.db.query(RawIngestionRecord).count(),1)

 def test_import_treats_canonical_name_variant_as_duplicate(self):
  existing = Match(
   date=date(2026, 1, 2),
   tournament='MODUS',
   stage='Historical',
   match_format='Best of 7',
   status='completed',
   player_a='Noa-Lynn van_Leuven_',
   player_b='B Two',
   winner='Noa-Lynn van_Leuven_',
   score='4-2',
  )
  self.db.add(existing)
  self.db.commit()

  content = (
   b'date,external_id,tournament,player_a,player_b,winner,score\n'
   b'2026-01-02,m2,MODUS,Noa-Lynn van Leuven,B Two,Noa-Lynn van Leuven,4-2\n'
  )
  batch = import_rows(
   self.db,
   parse_upload('x.csv', content),
   'x.csv',
  )

  self.assertEqual(batch.created_matches, 0)
  self.assertEqual(batch.duplicate_matches, 1)
  self.assertEqual(self.db.query(Match).count(), 1)

 def test_repeat_import_is_duplicate(self):
  rows=parse_upload('x.csv',self.sample()); import_rows(self.db,rows,'x.csv'); b=import_rows(self.db,rows,'x.csv'); self.assertEqual(b.created_matches,0); self.assertEqual(b.duplicate_matches,1)
 def test_json_supported(self):
  rows=parse_upload('x.json',b'[{"date":"2026-01-02","player_a":"A","player_b":"B"}]'); self.assertEqual(len(rows),1)
 def test_rollback_removes_only_created_records(self):
  batch=import_rows(self.db,parse_upload('x.csv',self.sample()),'x.csv'); rollback_batch(self.db,batch.id); self.assertEqual(self.db.query(Match).count(),0); self.assertEqual(self.db.query(HistoricalImportBatch).first().status,'rolled_back')
if __name__=='__main__': unittest.main()
