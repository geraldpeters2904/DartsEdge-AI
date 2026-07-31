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
from app.services.import_pipeline_service import (
    ImportPipelineService,
)
from tests.helpers.database import create_test_session


COMPLETE = Path("tests/fixtures/modus_folder_complete")


class ImportPipelineServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        self.queue_service = HistoricalImportQueueService()
        self.engine_service = HistoricalImportEngineService()
        self.service = ImportPipelineService()

    def tearDown(self):
        self.db.close()

    def prepare_queue(self, root):
        folder = Path(root) / "Group_A"
        shutil.copytree(COMPLETE, folder)

        self.queue_service.create(
            root=root,
            selected_folders=[str(folder)],
        )

        return folder

    def test_no_queue_or_engine_returns_empty_pipeline(self):
        with tempfile.TemporaryDirectory() as root:
            pipeline = self.service.build(self.db, root)

        self.assertFalse(pipeline.queue_exists)
        self.assertFalse(pipeline.engine_exists)
        self.assertIsNone(pipeline.queue)
        self.assertIsNone(pipeline.engine)

    def test_queue_exists_without_engine(self):
        with tempfile.TemporaryDirectory() as root:
            self.prepare_queue(root)

            pipeline = self.service.build(self.db, root)

        self.assertTrue(pipeline.queue_exists)
        self.assertFalse(pipeline.engine_exists)
        self.assertEqual(pipeline.queue.total_count, 1)
        self.assertEqual(pipeline.queue.remaining_count, 1)
        self.assertIsNotNone(pipeline.next_queue_item)

    def test_queue_and_engine_are_loaded(self):
        with tempfile.TemporaryDirectory() as root:
            self.prepare_queue(root)
            self.engine_service.start(self.db, root)

            pipeline = self.service.build(self.db, root)

        self.assertTrue(pipeline.queue_exists)
        self.assertTrue(pipeline.engine_exists)
        self.assertEqual(pipeline.engine.status, "running")
        self.assertEqual(pipeline.engine.total_count, 1)
        self.assertEqual(pipeline.engine.remaining_count, 1)
        self.assertIsNotNone(pipeline.next_engine_item)

    def test_completed_engine_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            self.prepare_queue(root)
            self.engine_service.start(self.db, root)

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

            pipeline = self.service.build(self.db, root)

        self.assertTrue(pipeline.engine_exists)
        self.assertEqual(pipeline.engine.status, "completed")
        self.assertEqual(pipeline.engine.completed_count, 1)
        self.assertIsNone(pipeline.next_engine_item)


if __name__ == "__main__":
    unittest.main()
