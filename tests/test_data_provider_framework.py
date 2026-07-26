import unittest
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import app
from app.models.match import Match
from app.providers.base import DataProvider, ProviderCapabilities, ProviderHealth
from app.providers.registry import ProviderRegistry
from app.services.data_provider_service import DataProviderService


class DummyProvider(DataProvider):
    provider_id = "dummy"
    display_name = "Dummy"
    description = "Test provider"
    capabilities = ProviderCapabilities(fixtures=False)

    def health(self):
        return ProviderHealth("healthy", "ok")


class DataProviderFrameworkTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def test_registry_rejects_duplicate_ids(self):
        registry = ProviderRegistry()
        registry.register(DummyProvider())
        with self.assertRaises(ValueError):
            registry.register(DummyProvider())

    def test_manual_provider_reports_capabilities(self):
        db = self.Session()
        try:
            status = DataProviderService(db).provider_status()[0]
            self.assertEqual(status["id"], "manual")
            self.assertTrue(status["capabilities"]["fixtures"])
            self.assertFalse(status["capabilities"]["odds"])
        finally:
            db.close()

    def test_fixture_preview_returns_existing_fixture(self):
        db = self.Session()
        try:
            db.add(Match(date=date.today(), tournament="MODUS", player_a="A", player_b="B", status="scheduled"))
            db.commit()
            preview = DataProviderService(db).fixture_preview(days=1)
            self.assertEqual(preview["count"], 1)
            self.assertEqual(preview["fixtures"][0].external_id, "manual:1")
        finally:
            db.close()

    def test_provider_api_route(self):
        response = TestClient(app).get("/api/data-providers")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["registered"], 1)

    def test_provider_page_route(self):
        response = TestClient(app).get("/data-providers")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Data Provider Framework", response.text)


if __name__ == "__main__":
    unittest.main()
