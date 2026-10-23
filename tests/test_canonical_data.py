import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.services.canonical_data_service import store_raw, map_entity, record_provenance, summary
class T(unittest.TestCase):
 def setUp(self):
  e=create_engine('sqlite:///:memory:'); Base.metadata.create_all(e); self.db=sessionmaker(bind=e)()
 def tearDown(self): self.db.close()
 def test_raw_dedup(self):
  _,a=store_raw(self.db,'modus','fixture','x',{'a':1}); _,b=store_raw(self.db,'modus','fixture','x',{'a':1}); self.assertTrue(a); self.assertFalse(b)
 def test_raw_versions(self):
  store_raw(self.db,'modus','result','x',{'score':'4-2'}); store_raw(self.db,'modus','result','x',{'score':'4-3'}); self.assertEqual(summary(self.db)['raw_records'],2)
 def test_mapping(self): self.assertEqual(map_entity(self.db,'sportradar','player','sr:1',7,'PDC').internal_id,7)
 def test_provenance(self): self.assertEqual(record_provenance(self.db,'match',3,'winner','modus').provider,'modus')
 def test_helpers_preserve_outer_transaction(self):
  from app.models.canonical_data import RawIngestionRecord, ProviderEntityMapping, DataProvenance

  self.db.connection().exec_driver_sql("BEGIN")
  with self.db.begin_nested():
   store_raw(self.db, 'modus', 'result', 'transaction-test', {'score': '4-2'})
   map_entity(self.db, 'modus', 'fixture', 'transaction-test', 123, 'MODUS')
   record_provenance(self.db, 'match', 123, 'winner', 'modus')

  self.assertTrue(self.db.in_transaction(), "Helpers must not commit the caller's transaction")
  self.db.rollback()

  self.assertEqual(self.db.query(RawIngestionRecord).count(), 0)
  self.assertEqual(self.db.query(ProviderEntityMapping).count(), 0)
  self.assertEqual(self.db.query(DataProvenance).count(), 0)

 def test_competitions(self): self.assertIn('WDF',summary(self.db)['supported_competitions'])
if __name__=='__main__': unittest.main()
