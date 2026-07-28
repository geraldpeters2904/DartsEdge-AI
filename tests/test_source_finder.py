import unittest

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.services.source_finder_service import SourceFinderService
from tests.helpers.database import create_test_session


class SourceFinderServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = SourceFinderService()

    def test_all_required_entity_types_have_sources(self):
        self.assertEqual(self.service.missing_coverage(), [])

    def test_official_modus_is_preferred_for_results(self):
        plan = self.service.coverage_plan()
        self.assertEqual(plan["results"][0].source_id, "modus-official")

    def test_odds_sources_are_filterable(self):
        sources = self.service.sources("odds")
        self.assertGreaterEqual(len(sources), 2)
        self.assertTrue(all(source.supports("odds") for source in sources))

    def test_invalid_entity_type_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.sources("players")


class SourceFinderRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_source_finder_page_returns_200(self):
        response = self.client.get("/admin/research/sources")
        self.assertEqual(response.status_code, 200)
        self.assertIn("MODUS Source Finder", response.text)
        self.assertIn("MODUS Super Series — Official Match Centre", response.text)

    def test_source_finder_filters_statistics(self):
        response = self.client.get("/admin/research/sources?entity_type=statistics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sources for Statistics", response.text)
        self.assertIn("Sources for Statistics", response.text)
        self.assertIn("Livesport", response.text)

    def test_research_workspace_links_to_source_finder(self):
        response = self.client.get("/admin/research")
        self.assertEqual(response.status_code, 200)
        self.assertIn("/admin/research/sources", response.text)
        self.assertIn("Find MODUS sources", response.text)


if __name__ == "__main__":
    unittest.main()
