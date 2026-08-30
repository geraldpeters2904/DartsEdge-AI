import unittest
from pathlib import Path

from app.models.historical_import import (
    HistoricalImportPreview,
)
from app.models.match import Match
from app.services.automatic_modus_fixture_import_service import (
    AutomaticModusFixtureImportService,
)
from tests.helpers.database import create_test_session


UPCOMING = Path(
    "tests/fixtures/modus_fixture_lifecycle/upcoming.html"
)
COMPLETED = Path(
    "tests/fixtures/modus_fixture_lifecycle/completed.html"
)


class AutomaticModusFixtureImportServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.db = create_test_session()
        self.service = AutomaticModusFixtureImportService()

    def tearDown(self):
        self.db.close()

    def test_imports_upcoming_fixture(self):
        result = self.service.import_html(
            self.db,
            html_text=UPCOMING.read_text(
                encoding="utf-8"
            ),
        )

        self.assertTrue(result.successful)
        self.assertEqual(result.fixture_count, 1)
        self.assertEqual(result.scheduled_count, 1)
        self.assertEqual(result.completed_count, 0)
        self.assertEqual(result.created_matches, 1)
        self.assertEqual(result.rejected_rows, 0)

        match = self.db.query(Match).one()
        self.assertEqual(match.status, "scheduled")

    def test_repeat_import_is_duplicate_safe(self):
        html = UPCOMING.read_text(encoding="utf-8")

        first = self.service.import_html(
            self.db,
            html_text=html,
        )
        second = self.service.import_html(
            self.db,
            html_text=html,
        )

        self.assertEqual(first.created_matches, 1)
        self.assertEqual(second.created_matches, 0)
        self.assertEqual(second.duplicate_matches, 1)
        self.assertEqual(self.db.query(Match).count(), 1)

    def test_completed_page_is_rejected_before_fixture_commit(self):
        self.service.import_html(
            self.db,
            html_text=UPCOMING.read_text(
                encoding="utf-8"
            ),
        )

        match = self.db.query(Match).one()
        self.assertEqual(match.status, "scheduled")

        preview_count_before = (
            self.db.query(HistoricalImportPreview).count()
        )

        with self.assertRaisesRegex(
            ValueError,
            "fixture-only import cannot commit completed fixture cards",
        ):
            self.service.import_html(
                self.db,
                html_text=COMPLETED.read_text(
                    encoding="utf-8"
                ),
            )

        self.assertEqual(self.db.query(Match).count(), 1)
        self.assertEqual(
            self.db.query(Match).one().status,
            "scheduled",
        )
        self.assertEqual(
            self.db.query(HistoricalImportPreview).count(),
            preview_count_before,
        )

    def test_marks_preview_committed(self):
        result = self.service.import_html(
            self.db,
            html_text=UPCOMING.read_text(
                encoding="utf-8"
            ),
        )

        preview = (
            self.db.query(HistoricalImportPreview)
            .filter_by(
                preview_uuid=result.preview_uuid
            )
            .one()
        )

        self.assertEqual(preview.status, "committed")
        self.assertEqual(preview.batch_id, result.batch_id)
        self.assertIsNotNone(preview.committed_at)

    def test_blank_html_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "must not be blank",
        ):
            self.service.import_html(
                self.db,
                html_text=" ",
            )


if __name__ == "__main__":
    unittest.main()
