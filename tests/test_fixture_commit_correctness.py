import tempfile
import unittest
from pathlib import Path

from app.collector.commit_bridge import CollectorCommitBridge
from app.collector.folder_preview import CollectorFolderPreviewService
from app.models.canonical_data import ProviderEntityMapping
from app.models.historical_import import HistoricalImportItem
from app.models.match import Match
from app.models.match_player_stats import MatchPlayerStats
from app.services.historical_import_service import rollback_batch
from tests.helpers.database import create_test_session


SCHEDULED = (
    "external_id,competition_code,competition_name,"
    "scheduled_at,status,match_format,"
    "player_a_external_id,player_a_name,"
    "player_b_external_id,player_b_name\n"
    "modus-match-20001,MODUS,MODUS Super Series,"
    "2026-07-28T10:00:00,scheduled,Best of 7,"
    "modus-player-one,Player One,modus-player-two,Player Two\n"
)

RESCHEDULED = (
    "external_id,competition_code,competition_name,"
    "scheduled_at,status,match_format,"
    "player_a_external_id,player_a_name,"
    "player_b_external_id,player_b_name\n"
    "modus-match-20001,MODUS,MODUS Super Series,"
    "2026-07-29T10:00:00,scheduled,Best of 7,"
    "modus-player-one,Player One,modus-player-two,Player Two\n"
)


class FixtureCommitCorrectnessTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        self.preview_service = CollectorFolderPreviewService()
        self.bridge = CollectorCommitBridge()

    def tearDown(self):
        self.db.close()

    def commit_csv(self, directory, content):
        path = Path(directory) / "fixtures.csv"
        path.write_text(content, encoding="utf-8")
        preview = self.preview_service.preview(
            folder=Path(directory),
            provider="modus-official",
        )
        return self.bridge.commit(db=self.db, preview=preview)

    def test_scheduled_fixture_creates_no_placeholder_statistics(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self.commit_csv(directory, SCHEDULED)

        self.assertEqual(report.created_matches, 1)
        self.assertEqual(self.db.query(Match).count(), 1)
        self.assertEqual(self.db.query(MatchPlayerStats).count(), 0)

    def test_repeat_fixture_uses_provider_external_id(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.commit_csv(directory, SCHEDULED)
            second = self.commit_csv(directory, SCHEDULED)

        self.assertEqual(first.created_matches, 1)
        self.assertEqual(second.created_matches, 0)
        self.assertEqual(second.duplicate_matches, 1)
        self.assertEqual(self.db.query(Match).count(), 1)

        mapping = (
            self.db.query(ProviderEntityMapping)
            .filter_by(
                provider="modus-official",
                entity_type="fixture",
                external_id="modus-match-20001",
            )
            .one()
        )
        self.assertEqual(mapping.internal_id, self.db.query(Match).one().id)

    def test_changed_fixture_updates_existing_match(self):
        with tempfile.TemporaryDirectory() as directory:
            self.commit_csv(directory, SCHEDULED)
            updated = self.commit_csv(directory, RESCHEDULED)

        self.assertEqual(updated.created_matches, 0)
        self.assertEqual(self.db.query(Match).count(), 1)
        self.assertEqual(
            self.db.query(Match).one().date.isoformat(),
            "2026-07-29",
        )

        item = (
            self.db.query(HistoricalImportItem)
            .filter_by(entity_type="fixture", action="updated")
            .one()
        )
        self.assertEqual(item.external_id, "modus-match-20001")

    def test_cancelled_fixture_is_not_resurrected_by_old_scheduled_feed(self):
        with tempfile.TemporaryDirectory() as directory:
            self.commit_csv(directory, SCHEDULED)

            match = self.db.query(Match).one()
            match.status = "cancelled"
            self.db.commit()

            repeated = self.commit_csv(directory, SCHEDULED)

        match = self.db.query(Match).one()

        self.assertEqual(match.status, "cancelled")
        self.assertEqual(repeated.created_matches, 0)
        self.assertEqual(repeated.duplicate_matches, 1)

        item = (
            self.db.query(HistoricalImportItem)
            .filter_by(
                entity_type="fixture",
                action="duplicate",
            )
            .order_by(HistoricalImportItem.id.desc())
            .first()
        )

        self.assertIsNotNone(item)
        self.assertIn(
            "cancelled",
            (item.detail or "").lower(),
        )


    def test_rollback_restores_updated_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            self.commit_csv(directory, SCHEDULED)
            updated = self.commit_csv(directory, RESCHEDULED)

        rollback_batch(self.db, updated.batch_id)

        match = self.db.query(Match).one()
        self.assertEqual(match.date.isoformat(), "2026-07-28")
        self.assertEqual(match.status, "scheduled")

    def test_rollback_removes_new_fixture_without_stats(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self.commit_csv(directory, SCHEDULED)

        rollback_batch(self.db, report.batch_id)

        self.assertEqual(self.db.query(Match).count(), 0)
        self.assertEqual(self.db.query(MatchPlayerStats).count(), 0)


if __name__ == "__main__":
    unittest.main()
