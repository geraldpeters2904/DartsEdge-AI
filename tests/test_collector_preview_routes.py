import unittest

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models.historical_import import (
    HistoricalImportPreview,
)
from tests.helpers.database import create_test_session


FIXTURES = (
    "external_id,competition_code,competition_name,"
    "scheduled_at,status,match_format,"
    "player_a_external_id,player_a_name,"
    "player_b_external_id,player_b_name\n"
    "match-1,MODUS,MODUS Super Series,"
    "2026-07-28T10:00:00,scheduled,Best of 7,"
    "player-a,Player A,player-b,Player B\n"
)


class CollectorPreviewRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def create_fixture_preview(self):
        return self.client.post(
            "/admin/collector/preview",
            data={
                "provider": "manual-research",
                "competition": "MODUS",
            },
            files={
                "fixtures_file": (
                    "fixtures.csv",
                    FIXTURES,
                    "text/csv",
                ),
            },
            follow_redirects=False,
        )

    def test_dashboard_form_posts_to_preview_route(self):
        response = self.client.get("/admin/collector")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'action="/admin/collector/preview"',
            response.text,
        )
        self.assertIn(
            'type="submit"',
            response.text,
        )

    def test_valid_upload_creates_persisted_preview(self):
        response = self.create_fixture_preview()

        self.assertEqual(response.status_code, 303)
        self.assertIn(
            "/admin/collector/preview/",
            response.headers["location"],
        )

        preview = (
            self.db.query(HistoricalImportPreview)
            .one()
        )

        self.assertEqual(preview.provider, "manual-research")
        self.assertEqual(preview.competition_code, "MODUS")
        self.assertEqual(preview.status, "pending")
        self.assertIn("fixtures.csv", preview.filename)

    def test_preview_page_displays_quality_and_file_status(self):
        response = self.create_fixture_preview()
        location = response.headers["location"]

        preview_response = self.client.get(location)

        self.assertEqual(
            preview_response.status_code,
            200,
        )
        self.assertIn(
            "Review collection session",
            preview_response.text,
        )
        self.assertIn("100.0%", preview_response.text)
        self.assertIn("fixtures.csv", preview_response.text)
        self.assertIn("Ready to commit", preview_response.text)

    def test_upload_requires_at_least_one_file(self):
        response = self.client.post(
            "/admin/collector/preview",
            data={
                "provider": "manual-research",
                "competition": "MODUS",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertTrue(
            response.headers["location"].startswith(
                "/admin/collector?message="
            )
        )
        self.assertEqual(
            self.db.query(
                HistoricalImportPreview
            ).count(),
            0,
        )

    def test_invalid_csv_is_persisted_for_review(self):
        invalid = (
            "external_id,competition_code\n"
            "match-1,MODUS\n"
        )

        response = self.client.post(
            "/admin/collector/preview",
            data={
                "provider": "manual-research",
                "competition": "MODUS",
            },
            files={
                "fixtures_file": (
                    "fixtures.csv",
                    invalid,
                    "text/csv",
                ),
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)

        page = self.client.get(
            response.headers["location"]
        )

        self.assertEqual(page.status_code, 200)
        self.assertIn(
            "Preview requires attention",
            page.text,
        )
        self.assertIn("Invalid", page.text)

    def test_cancel_marks_preview_cancelled(self):
        response = self.create_fixture_preview()

        preview = (
            self.db.query(HistoricalImportPreview)
            .one()
        )

        cancel_response = self.client.post(
            (
                "/admin/collector/preview/"
                f"{preview.preview_uuid}/cancel"
            ),
            follow_redirects=False,
        )

        self.assertEqual(
            cancel_response.status_code,
            303,
        )

        self.db.refresh(preview)
        self.assertEqual(preview.status, "cancelled")

    def test_missing_preview_redirects_to_collector(self):
        response = self.client.get(
            "/admin/collector/preview/missing",
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertTrue(
            response.headers["location"].startswith(
                "/admin/collector?message="
            )
        )


if __name__ == "__main__":
    unittest.main()
