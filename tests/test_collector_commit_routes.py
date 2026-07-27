import unittest

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportPreview,
)
from app.models.match import Match
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


INVALID_FIXTURES = (
    "external_id,competition_code\n"
    "match-1,MODUS\n"
)


class CollectorCommitRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = (
            override_get_db
        )

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()

    def create_preview(self, content=FIXTURES):
        response = self.client.post(
            "/admin/collector/preview",
            data={
                "provider": "manual-research",
                "competition": "MODUS",
            },
            files={
                "fixtures_file": (
                    "fixtures.csv",
                    content,
                    "text/csv",
                ),
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)

        return (
            self.db.query(HistoricalImportPreview)
            .order_by(
                HistoricalImportPreview.id.desc()
            )
            .first()
        )

    def test_ready_preview_displays_commit_button(self):
        preview = self.create_preview()

        response = self.client.get(
            (
                "/admin/collector/preview/"
                f"{preview.preview_uuid}"
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            (
                f"/admin/collector/preview/"
                f"{preview.preview_uuid}/commit"
            ),
            response.text,
        )
        self.assertIn(
            "Commit import",
            response.text,
        )

    def test_commit_creates_batch_and_match(self):
        preview = self.create_preview()

        response = self.client.post(
            (
                "/admin/collector/preview/"
                f"{preview.preview_uuid}/commit"
            ),
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertTrue(
            response.headers["location"].startswith(
                "/admin/collector?message="
            )
        )

        self.db.refresh(preview)

        self.assertEqual(preview.status, "committed")
        self.assertIsNotNone(preview.batch_id)
        self.assertIsNotNone(preview.committed_at)
        self.assertEqual(
            self.db.query(Match).count(),
            1,
        )
        self.assertEqual(
            self.db.query(
                HistoricalImportBatch
            ).count(),
            1,
        )

    def test_invalid_preview_cannot_be_committed(self):
        preview = self.create_preview(
            INVALID_FIXTURES
        )

        response = self.client.post(
            (
                "/admin/collector/preview/"
                f"{preview.preview_uuid}/commit"
            ),
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertTrue(
            response.headers["location"].startswith(
                (
                    "/admin/collector/preview/"
                    f"{preview.preview_uuid}?message="
                )
            )
        )
        self.assertEqual(
            self.db.query(Match).count(),
            0,
        )

        self.db.refresh(preview)
        self.assertEqual(preview.status, "pending")

    def test_committed_preview_cannot_be_committed_twice(self):
        preview = self.create_preview()

        commit_url = (
            "/admin/collector/preview/"
            f"{preview.preview_uuid}/commit"
        )

        first = self.client.post(
            commit_url,
            follow_redirects=False,
        )
        second = self.client.post(
            commit_url,
            follow_redirects=False,
        )

        self.assertEqual(first.status_code, 303)
        self.assertEqual(second.status_code, 303)
        self.assertEqual(
            self.db.query(Match).count(),
            1,
        )
        self.assertEqual(
            self.db.query(
                HistoricalImportBatch
            ).count(),
            1,
        )

    def test_dashboard_displays_rollback_action(self):
        preview = self.create_preview()

        self.client.post(
            (
                "/admin/collector/preview/"
                f"{preview.preview_uuid}/commit"
            ),
            follow_redirects=False,
        )

        batch = (
            self.db.query(HistoricalImportBatch)
            .one()
        )

        response = self.client.get(
            "/admin/collector"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            (
                f"/admin/collector/batches/"
                f"{batch.id}/rollback"
            ),
            response.text,
        )
        self.assertIn("Rollback", response.text)

    def test_rollback_removes_data_and_updates_statuses(self):
        preview = self.create_preview()

        self.client.post(
            (
                "/admin/collector/preview/"
                f"{preview.preview_uuid}/commit"
            ),
            follow_redirects=False,
        )

        batch = (
            self.db.query(HistoricalImportBatch)
            .one()
        )

        response = self.client.post(
            (
                "/admin/collector/batches/"
                f"{batch.id}/rollback"
            ),
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(
            self.db.query(Match).count(),
            0,
        )

        self.db.refresh(batch)
        self.db.refresh(preview)

        self.assertEqual(
            batch.status,
            "rolled_back",
        )
        self.assertEqual(
            preview.status,
            "rolled_back",
        )

    def test_cancelled_preview_cannot_be_committed(self):
        preview = self.create_preview()

        self.client.post(
            (
                "/admin/collector/preview/"
                f"{preview.preview_uuid}/cancel"
            ),
            follow_redirects=False,
        )

        response = self.client.post(
            (
                "/admin/collector/preview/"
                f"{preview.preview_uuid}/commit"
            ),
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(
            self.db.query(Match).count(),
            0,
        )


if __name__ == "__main__":
    unittest.main()
