import unittest
from fastapi.testclient import TestClient
from app.db import get_db
from app.main import app
from app.models.historical_import import HistoricalImportPreview
from app.services.research_workspace_service import ResearchWorkspaceService
from tests.helpers.database import create_test_session


class ResearchWorkspaceServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ResearchWorkspaceService()

    def test_detects_tab_separated_table(self):
        table = self.service.parse_table("external_id\tcompetition_code\nmatch-1\tMODUS\n")
        self.assertEqual(table.delimiter, "\t")
        self.assertEqual(table.headers, ["external_id", "competition_code"])

    def test_suggests_common_fixture_headers(self):
        mapping = self.service.suggested_mapping("fixtures", ["Match ID", "Player 1", "Player 2"])
        self.assertEqual(mapping["Match ID"], "external_id")
        self.assertEqual(mapping["Player 1"], "player_a_name")

    def test_fractional_odds_are_normalised(self):
        self.assertEqual(self.service._normalise_value("decimal_odds", "5/4"), "2.25")


class ResearchWorkspaceRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        def override_get_db():
            yield self.db
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def test_workspace_page_loads(self):
        response = self.client.get("/admin/research")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Research Workspace", response.text)

    def test_mapping_preview_loads(self):
        raw = (
            "external_id,competition_code,competition_name,scheduled_at,"
            "player_a_external_id,player_a_name,player_b_external_id,player_b_name\n"
            "match-1,MODUS,MODUS Super Series,2026-07-28T10:00:00,"
            "player-a,Player A,player-b,Player B\n"
        )
        response = self.client.post("/admin/research/preview", data={
            "entity_type": "fixtures", "provider": "manual-research",
            "competition": "MODUS", "raw_text": raw,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("Map pasted columns", response.text)

    def test_save_session_and_send_to_collector_preview(self):
        raw = (
            "external_id,competition_code,competition_name,scheduled_at,"
            "player_a_external_id,player_a_name,player_b_external_id,player_b_name\n"
            "match-1,MODUS,MODUS Super Series,2026-07-28T10:00:00,"
            "player-a,Player A,player-b,Player B\n"
        )
        headers = raw.splitlines()[0].split(",")
        data = {
            "entity_type": "fixtures", "provider": "manual-research",
            "competition": "MODUS", "raw_text": raw,
            "header_count": str(len(headers)),
        }
        for i, header in enumerate(headers):
            data[f"header_{i}"] = header
            data[f"map_{i}"] = header
        response = self.client.post("/admin/research/save", data=data, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        preview = self.db.query(HistoricalImportPreview).filter_by(status="research").one()
        response = self.client.post(
            f"/admin/research/{preview.preview_uuid}/collector-preview",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertIn("/admin/collector/preview/", response.headers["location"])


if __name__ == "__main__":
    unittest.main()
