import unittest

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportItem,
)
from app.models.match import Match
from app.services.warehouse_explorer_service import WarehouseExplorerService
from tests.helpers.database import create_test_session


class WarehouseExplorerServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        self.service = WarehouseExplorerService()

    def tearDown(self):
        self.db.close()

    def create_batch(self):
        batch = HistoricalImportBatch(
            batch_uuid="batch-0001",
            filename="modus-bundle",
            provider="modus-official",
            competition_code="MODUS",
            status="imported",
            received_rows=3,
            created_matches=1,
        )
        self.db.add(batch)
        self.db.flush()

        match = Match(
            player_a="Player One",
            player_b="Player Two",
            tournament="MODUS Super Series",
            stage="Group A",
            status="completed",
            score="4-2",
        )
        self.db.add(match)
        self.db.flush()

        self.db.add(
            HistoricalImportItem(
                batch_id=batch.id,
                entity_type="match",
                internal_id=match.id,
                external_id="modus-match-20001",
                action="created",
                created_by_batch=True,
            )
        )
        self.db.commit()
        return batch

    def test_lists_batches_newest_first(self):
        batch = self.create_batch()

        batches = self.service.list_batches(self.db)

        self.assertEqual(batches[0].id, batch.id)

    def test_batch_detail_resolves_match_record(self):
        batch = self.create_batch()

        detail = self.service.batch_detail(self.db, batch.id)

        self.assertIsNotNone(detail)
        self.assertEqual(detail.created_count, 1)
        self.assertEqual(
            detail.items[0].match.player_a,
            "Player One",
        )

    def test_missing_batch_returns_none(self):
        self.assertIsNone(self.service.batch_detail(self.db, 999999))


class WarehouseExplorerRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_explorer_page_returns_200(self):
        response = self.client.get("/admin/warehouse")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Warehouse Explorer", response.text)
        self.assertIn("Committed and rolled-back batches", response.text)

    def test_batch_detail_page_returns_200(self):
        batch = HistoricalImportBatch(
            batch_uuid="batch-0002",
            filename="bundle",
            provider="modus-official",
            competition_code="MODUS",
            status="imported",
            received_rows=0,
        )
        self.db.add(batch)
        self.db.commit()

        response = self.client.get(
            f"/admin/warehouse/batches/{batch.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Batch batch-00", response.text)
        self.assertIn("Stable external-ID mappings", response.text)
        self.assertIn("Field-level source trace", response.text)


if __name__ == "__main__":
    unittest.main()
