import tempfile
import unittest
from pathlib import Path

from app.collector.commit_bridge import CollectorCommitBridge
from app.collector.folder_preview import CollectorFolderPreviewService
from app.models.canonical_data import (
    DataProvenance,
    ProviderEntityMapping,
    RawIngestionRecord,
)
from app.models.historical_import import (
    HistoricalImportBatch,
    HistoricalImportItem,
    PlayerAlias,
)
from app.models.match import Match
from app.models.match_player_stats import MatchPlayerStats
from app.models.player import Player
from app.services.historical_import_service import rollback_batch
from tests.helpers.database import create_test_session


VALID_FIXTURES = (
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


class CollectorFixtureCommitTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        self.preview_service = CollectorFolderPreviewService()
        self.bridge = CollectorCommitBridge()

    def tearDown(self):
        self.db.close()

    @staticmethod
    def write_fixture_file(directory, content=VALID_FIXTURES):
        path = Path(directory) / "fixtures.csv"
        path.write_text(content, encoding="utf-8")
        return path

    def build_preview(self, directory, content=VALID_FIXTURES):
        self.write_fixture_file(directory, content)

        return self.preview_service.preview(
            folder=Path(directory),
            provider="manual-research",
        )

    def test_valid_preview_creates_fixture_and_players(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(directory)
            report = self.bridge.commit(
                db=self.db,
                preview=preview,
            )

        self.assertEqual(report.created_matches, 1)
        self.assertEqual(report.created_players, 2)
        self.assertEqual(report.rejected_rows, 0)
        self.assertEqual(self.db.query(Match).count(), 1)
        self.assertEqual(self.db.query(Player).count(), 2)

        match = self.db.query(Match).one()

        self.assertEqual(match.player_a, "Player A")
        self.assertEqual(match.player_b, "Player B")
        self.assertEqual(match.status, "scheduled")
        self.assertEqual(match.tournament, "MODUS Super Series")

    def test_commit_creates_batch_and_import_items(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(directory)
            report = self.bridge.commit(
                db=self.db,
                preview=preview,
            )

        batch = self.db.query(HistoricalImportBatch).one()

        self.assertEqual(batch.id, report.batch_id)
        self.assertEqual(batch.provider, "manual-research")
        self.assertEqual(batch.competition_code, "MODUS")
        self.assertEqual(batch.received_rows, 1)
        self.assertEqual(batch.created_matches, 1)
        self.assertEqual(batch.created_players, 2)

        items = self.db.query(HistoricalImportItem).all()

        self.assertEqual(len(items), 3)
        self.assertEqual(
            {item.entity_type for item in items},
            {"player", "match"},
        )

    def test_commit_creates_aliases_and_all_provider_mappings(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(directory)
            self.bridge.commit(
                db=self.db,
                preview=preview,
            )

        self.assertEqual(self.db.query(PlayerAlias).count(), 2)

        mappings = self.db.query(ProviderEntityMapping).all()

        self.assertEqual(len(mappings), 5)

        fixture_mappings = [
            row
            for row in mappings
            if row.entity_type == "fixture"
        ]
        player_mappings = [
            row
            for row in mappings
            if row.entity_type == "player"
        ]

        self.assertEqual(len(fixture_mappings), 1)
        self.assertEqual(len(player_mappings), 4)

        fixture_mapping = fixture_mappings[0]

        self.assertEqual(fixture_mapping.external_id, "match-1")
        self.assertEqual(fixture_mapping.competition_code, "MODUS")

        external_ids = {
            mapping.external_id
            for mapping in player_mappings
        }

        self.assertEqual(
            external_ids,
            {
                "Player A",
                "Player B",
                "player-a",
                "player-b",
            },
        )

    def test_commit_stores_raw_data_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(directory)
            self.bridge.commit(
                db=self.db,
                preview=preview,
            )

        self.assertEqual(self.db.query(RawIngestionRecord).count(), 1)

        raw = self.db.query(RawIngestionRecord).one()

        self.assertEqual(raw.provider, "manual-research")
        self.assertEqual(raw.entity_type, "fixture")
        self.assertEqual(raw.external_id, "match-1")
        self.assertTrue(raw.processed)

        provenance = self.db.query(DataProvenance).all()

        self.assertGreaterEqual(len(provenance), 6)
        self.assertIn(
            "status",
            {record.field_name for record in provenance},
        )

    def test_fixture_commit_does_not_create_placeholder_statistics(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(directory)
            self.bridge.commit(
                db=self.db,
                preview=preview,
            )

        self.assertEqual(
            self.db.query(MatchPlayerStats).count(),
            0,
        )

    def test_repeat_commit_is_duplicate_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(directory)

            first = self.bridge.commit(
                db=self.db,
                preview=preview,
            )
            second = self.bridge.commit(
                db=self.db,
                preview=preview,
            )

        self.assertEqual(first.created_matches, 1)
        self.assertEqual(second.created_matches, 0)
        self.assertEqual(second.duplicate_matches, 1)
        self.assertEqual(self.db.query(Match).count(), 1)
        self.assertEqual(self.db.query(Player).count(), 2)

    def test_invalid_preview_is_not_committed(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(
                directory,
                content=INVALID_FIXTURES,
            )

            with self.assertRaises(ValueError):
                self.bridge.commit(
                    db=self.db,
                    preview=preview,
                )

        self.assertEqual(self.db.query(Match).count(), 0)
        self.assertEqual(self.db.query(Player).count(), 0)
        self.assertEqual(
            self.db.query(HistoricalImportBatch).count(),
            0,
        )

    def test_rollback_removes_created_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(directory)
            report = self.bridge.commit(
                db=self.db,
                preview=preview,
            )

        rollback_batch(self.db, report.batch_id)

        self.assertEqual(self.db.query(Match).count(), 0)
        self.assertEqual(
            self.db.query(MatchPlayerStats).count(),
            0,
        )

        batch = (
            self.db.query(HistoricalImportBatch)
            .filter_by(id=report.batch_id)
            .one()
        )

        self.assertEqual(batch.status, "rolled_back")

    def test_report_contains_fixture_entity_count(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(directory)

            report = self.bridge.commit(
                db=self.db,
                preview=preview,
                filename="manual-modus-fixtures.csv",
            )

        self.assertEqual(report.entity_counts["fixtures"], 1)
        self.assertEqual(report.entity_counts["results"], 0)
        self.assertEqual(report.entity_counts["statistics"], 0)
        self.assertEqual(report.entity_counts["odds"], 0)
        self.assertEqual(
            report.batch.filename,
            "manual-modus-fixtures.csv",
        )


if __name__ == "__main__":
    unittest.main()