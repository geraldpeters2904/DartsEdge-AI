import shutil
import tempfile
import unittest
from pathlib import Path

from app.models.canonical_data import ProviderEntityMapping
from app.services.historical_import_engine_service import (
    HistoricalImportEngineService,
)
from app.services.historical_import_queue_service import (
    HistoricalImportQueueService,
)
from tests.helpers.database import create_test_session


COMPLETE = Path("tests/fixtures/modus_folder_complete")


class HistoricalImportEngineTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        self.queue = HistoricalImportQueueService()
        self.engine = HistoricalImportEngineService()

    def tearDown(self):
        self.db.close()

    def prepare(self, root):
        folder = Path(root) / "Group_A"
        shutil.copytree(COMPLETE, folder)
        self.queue.create(root=root, selected_folders=[str(folder)])

    def test_start_and_resume(self):
        with tempfile.TemporaryDirectory() as root:
            self.prepare(root)
            state = self.engine.start(self.db, root)
            self.assertEqual(state.total_count, 1)
            resumed = self.engine.load(self.db, root)
            self.assertEqual(resumed.remaining_count, 1)

    def test_begin_next_tracks_attempt(self):
        with tempfile.TemporaryDirectory() as root:
            self.prepare(root)
            self.engine.start(self.db, root)
            state = self.engine.begin_next(self.db, root)
            self.assertEqual(state.items[0].state, "in_progress")
            self.assertEqual(state.items[0].attempts, 1)

    def test_mappings_complete_group(self):
        with tempfile.TemporaryDirectory() as root:
            self.prepare(root)
            self.engine.start(self.db, root)
            for match_id in (18195, 18196):
                self.db.add(
                    ProviderEntityMapping(
                        provider="modus-official",
                        entity_type="fixture",
                        external_id=f"modus-match-{match_id}",
                        internal_id=match_id,
                        competition_code="MODUS",
                    )
                )
            self.db.commit()
            state = self.engine.load(self.db, root)
            self.assertEqual(state.status, "completed")
            self.assertEqual(state.completed_count, 1)


if __name__ == "__main__":
    unittest.main()
