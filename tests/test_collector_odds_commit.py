import tempfile
import unittest
from pathlib import Path

from app.collector.commit_bridge import (
    CollectorCommitBridge,
)
from app.collector.folder_preview import (
    CollectorFolderPreviewService,
)
from app.models.canonical_data import (
    DataProvenance,
    ProviderEntityMapping,
    RawIngestionRecord,
)
from app.models.historical_import import (
    HistoricalImportItem,
)
from app.models.odds_snapshot import OddsSnapshot
from app.services.historical_import_service import (
    rollback_batch,
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

ODDS = (
    "match_external_id,market,selection_external_id,"
    "selection_name,bookmaker,decimal_odds,captured_at,"
    "source_provider,source_external_id,"
    "source_retrieved_at,source_competition_code,"
    "source_confidence\n"
    "match-1,match_winner,player-a,Player A,"
    "Example Bookmaker,1.80,2026-07-28T09:00:00,"
    "manual-odds,match-1:book:player-a:0900,"
    "2026-07-28T09:00:00,MODUS,manual\n"
    "match-1,match_winner,player-b,Player B,"
    "Example Bookmaker,2.10,2026-07-28T09:00:00,"
    "manual-odds,match-1:book:player-b:0900,"
    "2026-07-28T09:00:00,MODUS,manual\n"
)


class CollectorOddsCommitTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        self.preview_service = (
            CollectorFolderPreviewService()
        )
        self.bridge = CollectorCommitBridge()

    def tearDown(self):
        self.db.close()

    @staticmethod
    def write_file(
        directory,
        filename,
        content,
    ):
        path = Path(directory) / filename
        path.write_text(content, encoding="utf-8")
        return path

    def build_preview(
        self,
        directory,
        *,
        include_fixtures=True,
        odds=ODDS,
    ):
        if include_fixtures:
            self.write_file(
                directory,
                "fixtures.csv",
                FIXTURES,
            )

        self.write_file(
            directory,
            "odds.csv",
            odds,
        )

        return self.preview_service.preview(
            folder=Path(directory),
            provider="manual-odds",
        )

    def test_odds_create_two_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self.bridge.commit(
                db=self.db,
                preview=self.build_preview(directory),
            )

        rows = (
            self.db.query(OddsSnapshot)
            .order_by(OddsSnapshot.selection)
            .all()
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            report.entity_counts["odds"],
            2,
        )
        self.assertEqual(rows[0].selection, "Player A")
        self.assertEqual(rows[0].decimal_odds, 1.80)
        self.assertEqual(rows[1].selection, "Player B")
        self.assertEqual(rows[1].decimal_odds, 2.10)
        self.assertEqual(
            rows[0].tournament,
            "MODUS Super Series",
        )

    def test_player_external_id_resolves_selection(self):
        odds = ODDS.replace(
            ",Player A,Example Bookmaker,",
            ",Incorrect Name,Example Bookmaker,",
            1,
        )

        with tempfile.TemporaryDirectory() as directory:
            self.bridge.commit(
                db=self.db,
                preview=self.build_preview(
                    directory,
                    odds=odds,
                ),
            )

        row = (
            self.db.query(OddsSnapshot)
            .filter_by(decimal_odds=1.80)
            .one()
        )

        self.assertEqual(row.selection, "Player A")

    def test_identical_odds_are_duplicate_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            self.bridge.commit(
                db=self.db,
                preview=self.build_preview(directory),
            )

        with tempfile.TemporaryDirectory() as directory:
            report = self.bridge.commit(
                db=self.db,
                preview=self.build_preview(
                    directory,
                    include_fixtures=False,
                ),
            )

        self.assertEqual(
            self.db.query(OddsSnapshot).count(),
            2,
        )

        duplicates = (
            self.db.query(HistoricalImportItem)
            .filter_by(
                batch_id=report.batch_id,
                entity_type="odds_snapshot",
                action="duplicate",
            )
            .count()
        )

        self.assertEqual(duplicates, 2)

    def test_new_capture_time_creates_price_history(self):
        with tempfile.TemporaryDirectory() as directory:
            self.bridge.commit(
                db=self.db,
                preview=self.build_preview(directory),
            )

        later_odds = (
            ODDS
            .replace(
                "2026-07-28T09:00:00",
                "2026-07-28T09:05:00",
            )
            .replace(
                "player-a:0900",
                "player-a:0905",
            )
            .replace(
                "player-b:0900",
                "player-b:0905",
            )
        )

        with tempfile.TemporaryDirectory() as directory:
            self.bridge.commit(
                db=self.db,
                preview=self.build_preview(
                    directory,
                    include_fixtures=False,
                    odds=later_odds,
                ),
            )

        self.assertEqual(
            self.db.query(OddsSnapshot).count(),
            4,
        )

    def test_odds_store_raw_mapping_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            self.bridge.commit(
                db=self.db,
                preview=self.build_preview(directory),
            )

        self.assertEqual(
            self.db.query(RawIngestionRecord)
            .filter_by(entity_type="odds")
            .count(),
            2,
        )

        self.assertEqual(
            self.db.query(ProviderEntityMapping)
            .filter_by(entity_type="odds")
            .count(),
            2,
        )

        fields = {
            row.field_name
            for row in (
                self.db.query(DataProvenance)
                .filter_by(entity_type="odds")
                .all()
            )
        }

        self.assertEqual(
            fields,
            {
                "market",
                "selection",
                "bookmaker",
                "decimal_odds",
                "captured_at",
            },
        )

    def test_odds_without_fixture_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self.bridge.commit(
                db=self.db,
                preview=self.build_preview(
                    directory,
                    include_fixtures=False,
                ),
            )

        self.assertEqual(
            self.db.query(OddsSnapshot).count(),
            0,
        )
        self.assertEqual(report.rejected_rows, 2)

    def test_invalid_match_winner_selection_is_rejected(self):
        invalid_odds = (
            ODDS.replace(
                "player-a,Player A",
                "unknown-player,Unknown Player",
                1,
            )
        )

        with tempfile.TemporaryDirectory() as directory:
            report = self.bridge.commit(
                db=self.db,
                preview=self.build_preview(
                    directory,
                    odds=invalid_odds,
                ),
            )

        self.assertEqual(
            self.db.query(OddsSnapshot).count(),
            1,
        )
        self.assertEqual(report.rejected_rows, 1)

    def test_rollback_removes_created_odds(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self.bridge.commit(
                db=self.db,
                preview=self.build_preview(directory),
            )

        self.assertEqual(
            self.db.query(OddsSnapshot).count(),
            2,
        )

        rollback_batch(
            self.db,
            report.batch_id,
        )

        self.assertEqual(
            self.db.query(OddsSnapshot).count(),
            0,
        )


if __name__ == "__main__":
    unittest.main()
