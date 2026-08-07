import unittest
from pathlib import Path

from app.models.canonical_data import (
    ProviderEntityMapping,
)
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportPreview,
)
from app.models.match import Match
from app.models.player_match_performance import (
    PlayerMatchPerformance,
)
from app.services.automatic_modus_folder_import_service import (
    AutomaticModusFolderImportService,
)
from tests.helpers.database import create_test_session


FIXTURE_FOLDER = Path(
    "tests/fixtures/modus_folder_complete"
).resolve()


class AutomaticModusFolderImportServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.db = create_test_session()
        self.service = AutomaticModusFolderImportService()

    def tearDown(self):
        self.db.close()

    def test_imports_complete_modus_folder(self):
        result = self.service.import_folder(
            self.db,
            folder=FIXTURE_FOLDER,
        )

        self.assertTrue(result.successful)
        self.assertEqual(result.created_matches, 2)
        self.assertEqual(result.rejected_rows, 0)
        self.assertEqual(
            result.entity_counts,
            {
                "fixtures": 2,
                "results": 2,
                "statistics": 4,
                "odds": 0,
            },
        )
        self.assertEqual(
            self.db.query(Match).count(),
            2,
        )
        self.assertEqual(
            self.db.query(PlayerMatchPerformance).count(),
            4,
        )

    def test_marks_collector_preview_committed(self):
        result = self.service.import_folder(
            self.db,
            folder=FIXTURE_FOLDER,
        )

        preview = (
            self.db.query(HistoricalImportPreview)
            .filter_by(preview_uuid=result.preview_uuid)
            .one()
        )

        self.assertEqual(preview.status, "committed")
        self.assertEqual(preview.batch_id, result.batch_id)
        self.assertIsNotNone(preview.committed_at)

    def test_creates_import_batch_and_provider_mappings(self):
        result = self.service.import_folder(
            self.db,
            folder=FIXTURE_FOLDER,
        )

        batch = (
            self.db.query(HistoricalImportBatch)
            .filter_by(id=result.batch_id)
            .one()
        )

        self.assertEqual(batch.provider, "modus-official")
        self.assertEqual(batch.status, "imported")
        self.assertEqual(batch.created_matches, 2)

        fixture_mappings = (
            self.db.query(ProviderEntityMapping)
            .filter_by(
                provider="modus-official",
                entity_type="fixture",
            )
            .count()
        )

        self.assertEqual(fixture_mappings, 2)

    def test_repeat_import_is_duplicate_safe(self):
        first = self.service.import_folder(
            self.db,
            folder=FIXTURE_FOLDER,
        )
        second = self.service.import_folder(
            self.db,
            folder=FIXTURE_FOLDER,
        )

        self.assertEqual(first.created_matches, 2)
        self.assertEqual(second.created_matches, 0)
        self.assertEqual(second.duplicate_matches, 2)
        self.assertEqual(
            self.db.query(Match).count(),
            2,
        )

    def test_missing_folder_is_rejected(self):
        with self.assertRaises(
            (FileNotFoundError, ValueError)
        ):
            self.service.import_folder(
                self.db,
                folder="/tmp/dartsedge-missing-modus-folder",
            )


if __name__ == "__main__":
    unittest.main()
