import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.capture_discovery_service import CaptureDiscoveryService
from app.services.modus_capture_session_service import SESSION_FILENAME


RESULTS_FIXTURE = Path("tests/fixtures/modus_capture/series14_week01_group_a.html")


class CaptureDiscoveryServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = CaptureDiscoveryService()

    def test_empty_root_is_created(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / "new-root"
            report = self.service.discover(root)
            self.assertTrue(root.exists())
            self.assertEqual(report.discovered_session_files, 0)

    def test_repairs_folder_with_results_but_no_session(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "Series_14" / "Week_01" / "Group_A"
            folder.mkdir(parents=True)
            (folder / "results.html").write_bytes(RESULTS_FIXTURE.read_bytes())

            report = self.service.discover(root, repair=True)

            self.assertEqual(report.repaired_sessions, 1)
            self.assertTrue((folder / SESSION_FILENAME).exists())
            self.assertEqual(report.discovered_session_files, 1)

    def test_existing_session_is_not_recreated(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "Series_14" / "Week_01" / "Group_A"
            folder.mkdir(parents=True)
            (folder / "results.html").write_bytes(RESULTS_FIXTURE.read_bytes())

            first = self.service.discover(root, repair=True)
            second = self.service.discover(root, repair=True)

            self.assertEqual(first.repaired_sessions, 1)
            self.assertEqual(second.repaired_sessions, 0)

    def test_invalid_results_page_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "Broken"
            folder.mkdir()
            (folder / "results.html").write_text("<html>broken</html>", encoding="utf-8")

            report = self.service.discover(root, repair=True)

            self.assertEqual(report.repaired_sessions, 0)
            self.assertEqual(len(report.issues), 1)
            self.assertEqual(report.issues[0].code, "session_repair_failed")


class CaptureDiscoveryRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_discovery_route_redirects_to_library(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.post(
                "/admin/collector/captures/discover",
                data={"root": root},
                follow_redirects=False,
            )

            self.assertEqual(response.status_code, 303)
            self.assertIn("/admin/collector/captures?root=", response.headers["location"])

    def test_library_page_shows_discovery_button(self):
        with tempfile.TemporaryDirectory() as root:
            response = self.client.get("/admin/collector/captures", params={"root": root})

            self.assertEqual(response.status_code, 200)
            self.assertIn("Discover &amp; Repair", response.text)
            self.assertIn("AUTOMATIC DISCOVERY", response.text)


if __name__ == "__main__":
    unittest.main()
