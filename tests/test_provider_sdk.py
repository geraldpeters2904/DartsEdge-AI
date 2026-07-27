import unittest
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.collector.service import CollectorService
from app.db import Base
from app.main import app
from app.models.provider_sync import ProviderSyncRun
from app.providers.adapters.modus import ModusAdapter
from app.providers.contracts import CanonicalProviderRecord, ProviderAdapter, ProviderCapabilities, ProviderHealth
from app.providers.registry import ProviderRegistry


class HealthyFixtureAdapter(ProviderAdapter):
    provider_id = "test-feed"
    display_name = "Test feed"
    description = "Test"
    capabilities = ProviderCapabilities(fixtures=True)
    supported_competitions = {"PDC"}

    def health(self):
        return ProviderHealth("healthy", "ready")

    def fixtures(self, start_date, end_date):
        return [CanonicalProviderRecord("fixture", "fx-1", "PDC", {"date": str(start_date)})]


class ProviderSdkTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

    def test_registry_rejects_duplicate_provider_ids(self):
        registry = ProviderRegistry()
        registry.register(ModusAdapter())
        with self.assertRaises(ValueError):
            registry.register(ModusAdapter())

    def test_modus_adapter_is_disabled_until_configured(self):
        provider = ModusAdapter()
        self.assertEqual(provider.health().status, "disabled")
        self.assertIn("MODUS", provider.supported_competitions)

    def test_collector_records_successful_run(self):
        registry = ProviderRegistry()
        registry.register(HealthyFixtureAdapter())
        db = self.Session()
        result = CollectorService(registry).run(db, "test-feed", "fixtures", date.today(), date.today())
        self.assertEqual(result["status"], "success")
        run = db.query(ProviderSyncRun).one()
        self.assertEqual(run.records_accepted, 1)
        db.close()

    def test_collector_records_disabled_provider_failure(self):
        registry = ProviderRegistry()
        registry.register(ModusAdapter())
        db = self.Session()
        result = CollectorService(registry).run(db, "modus", "fixtures", date.today(), date.today())
        self.assertEqual(result["status"], "failed")
        self.assertIn("authorised MODUS", result["error"])
        db.close()

    def test_provider_api_and_page_return_200(self):
        client = TestClient(app)
        self.assertEqual(client.get("/admin/providers").status_code, 200)
        response = client.get("/api/providers")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["registered"], 2)


if __name__ == "__main__":
    unittest.main()
