import shutil
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from app.db import get_db
from app.main import app
from app.models.canonical_data import ProviderEntityMapping
from app.services.historical_import_queue_service import HistoricalImportQueueService, QUEUE_FILENAME
from tests.helpers.database import create_test_session

COMPLETE = Path("tests/fixtures/modus_folder_complete")
INCOMPLETE = Path("tests/fixtures/modus_folder_incomplete")

class HistoricalImportQueueServiceTests(unittest.TestCase):
    def setUp(self): self.db=create_test_session(); self.service=HistoricalImportQueueService()
    def tearDown(self): self.db.close()
    def prepare(self, root, name, fixture):
        dest=Path(root)/name; shutil.copytree(fixture,dest); return dest
    def test_creates_and_loads_queue(self):
        with tempfile.TemporaryDirectory() as root:
            folder=self.prepare(root,"Group_A",COMPLETE)
            path=self.service.create(root=root,selected_folders=[str(folder)])
            queue=self.service.load(self.db,root)
        self.assertEqual(path.name,QUEUE_FILENAME); self.assertEqual(queue.total_count,1); self.assertEqual(queue.remaining_count,1)
    def test_queue_completion_uses_stable_fixture_mappings(self):
        with tempfile.TemporaryDirectory() as root:
            folder=self.prepare(root,"Group_A",COMPLETE); self.service.create(root=root,selected_folders=[str(folder)])
            for match_id in (18195,18196): self.db.add(ProviderEntityMapping(provider="modus-official",entity_type="fixture",external_id=f"modus-match-{match_id}",internal_id=match_id,competition_code="MODUS"))
            self.db.commit(); queue=self.service.load(self.db,root)
        self.assertEqual(queue.completed_count,1); self.assertIsNone(queue.next_item)
    def test_rejects_folder_outside_root(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            folder=self.prepare(outside,"Group_A",COMPLETE)
            with self.assertRaisesRegex(ValueError,"outside"): self.service.create(root=root,selected_folders=[str(folder)])
    def test_clear_removes_queue_file(self):
        with tempfile.TemporaryDirectory() as root:
            folder=self.prepare(root,"Group_A",INCOMPLETE); self.service.create(root=root,selected_folders=[str(folder)])
            self.assertTrue(self.service.clear(root)); self.assertFalse(Path(root,QUEUE_FILENAME).exists())

class HistoricalImportQueueRouteTests(unittest.TestCase):
    def setUp(self):
        self.db=create_test_session()
        def override_get_db(): yield self.db
        app.dependency_overrides[get_db]=override_get_db; self.client=TestClient(app)
    def tearDown(self): app.dependency_overrides.clear(); self.db.close()
    def test_manager_page_contains_queue_controls(self):
        with tempfile.TemporaryDirectory() as root:
            shutil.copytree(INCOMPLETE,Path(root)/"Group_A")
            response=self.client.get("/admin/historical-imports",params={"root":root})
        self.assertEqual(response.status_code,200); self.assertIn("Create Import Queue",response.text); self.assertIn('name="selected_folders"',response.text)
    def test_import_wizard_accepts_prefilled_source_path(self):
        response=self.client.get("/admin/collector/import",params={"source_path":"/tmp/example-group"})
        self.assertEqual(response.status_code,200); self.assertIn('value="/tmp/example-group"',response.text)

if __name__ == "__main__": unittest.main()
