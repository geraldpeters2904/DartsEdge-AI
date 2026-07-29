import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models.canonical_data import ProviderEntityMapping
from app.services.historical_import_manager_service import (
    HistoricalImportManagerService,
)
from tests.helpers.database import create_test_session


COMPLETE = Path("tests/fixtures/modus_folder_complete")
INCOMPLETE = Path("tests/fixtures/modus_folder_incomplete")


class HistoricalImportManagerServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        self.service = HistoricalImportManagerService()

    def tearDown(self):
        self.db.close()

    def test_discovers_results_folders_recursively(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "Series_14" / "Week_13" / "Group_A"
            destination.parent.mkdir(parents=True)
            shutil.copytree(COMPLETE, destination)

            library = self.service.scan(self.db, root)

        self.assertEqual(library.discovered_count, 1)
        self.assertEqual(library.ready_count, 1)
        self.assertEqual(library.folders[0].series_label, "Series 14")
        self.assertEqual(library.folders[0].week_label, "Week 13")

    def test_incomplete_folder_is_identified(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "Group_A"
            shutil.copytree(INCOMPLETE, destination)

            library = self.service.scan(self.db, root)

        self.assertEqual(library.incomplete_count, 1)
        self.assertEqual(library.folders[0].status, "incomplete")

    def test_provider_mappings_mark_folder_partially_imported(self):
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "Group_A"
            shutil.copytree(COMPLETE, destination)

            self.db.add(
                ProviderEntityMapping(
                    provider="modus-official",
                    entity_type="fixture",
                    external_id="modus-match-18195",
                    internal_id=1,
                    competition_code="MODUS",
                )
            )
            self.db.commit()

            library = self.service.scan(self.db, root)

        self.assertEqual(library.partially_imported_count, 1)
        self.assertEqual(library.folders[0].imported_count, 1)

    def test_missing_root_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.service.scan(
                self.db,
                "/definitely/not/a/real/dartsedge/folder",
            )


class HistoricalImportManagerRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_page_returns_200(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get(
                "/admin/historical-imports",
                params={"root": root},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Historical Import Manager", response.text)
        self.assertIn("Scan Historical Library", response.text)


if __name__ == "__main__":
    unittest.main()
