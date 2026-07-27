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
 def test_competitions(self): self.assertIn('WDF',summary(self.db)['supported_competitions'])
if __name__=='__main__': unittest.main()
