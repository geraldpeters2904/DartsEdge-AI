import unittest

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class CollectorRouteTests(unittest.TestCase):
    def test_collector_page_returns_200(self):
        response = client.get("/admin/collector")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Data Collection Centre", response.text)

    def test_collector_page_lists_supported_files(self):
        response = client.get("/admin/collector")

        self.assertIn("fixtures.csv", response.text)
        self.assertIn("results.csv", response.text)
        self.assertIn("statistics.csv", response.text)
        self.assertIn("odds.csv", response.text)

    def test_collector_page_contains_collection_actions(self):
        response = client.get("/admin/collector")

        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/admin/collector/import"', response.text)
        self.assertIn('href="/admin/collector/capture/modus"', response.text)
        self.assertIn("Import Data", response.text)
        self.assertIn("MODUS Capture", response.text)


if __name__ == "__main__":
    unittest.main()
