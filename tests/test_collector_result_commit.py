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
)
from app.models.match import Match
from app.models.paper_trade import PaperTrade
from app.models.prediction import Prediction
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

RESULTS = (
    "match_external_id,player_a_external_id,"
    "player_b_external_id,winner_external_id,"
    "player_a_legs,player_b_legs,"
    "completed_at,first_leg_winner_external_id,"
    "first_180_player_external_id\n"
    "match-1,player-a,player-b,player-a,"
    "4,2,2026-07-28T10:28:00,"
    "player-a,player-b\n"
)


class CollectorResultCommitTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()
        self.preview_service = CollectorFolderPreviewService()
        self.bridge = CollectorCommitBridge()

    def tearDown(self):
        self.db.close()

    @staticmethod
    def write_file(directory, filename, content):
        path = Path(directory) / filename
        path.write_text(content, encoding="utf-8")
        return path

    def build_preview(
        self,
        directory,
        *,
        include_fixtures=True,
        results=RESULTS,
    ):
        if include_fixtures:
            self.write_file(
                directory,
                "fixtures.csv",
                FIXTURES,
            )

        self.write_file(
            directory,
            "results.csv",
            results,
        )

        return self.preview_service.preview(
            folder=Path(directory),
            provider="manual-research",
        )

    def test_fixture_and_result_commit_updates_one_match(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(directory)

            report = self.bridge.commit(
                db=self.db,
                preview=preview,
            )

        self.assertEqual(self.db.query(Match).count(), 1)
        self.assertEqual(report.entity_counts["fixtures"], 1)
        self.assertEqual(report.entity_counts["results"], 1)

        match = self.db.query(Match).one()

        self.assertEqual(match.status, "completed")
        self.assertEqual(match.winner, "Player A")
        self.assertEqual(match.score, "4-2")
        self.assertEqual(match.first_leg_winner, "Player A")
        self.assertEqual(match.first_180_player, "Player B")

    def test_result_settles_linked_match_winner_trade(self):
        with tempfile.TemporaryDirectory() as fixture_directory:
            self.write_file(
                fixture_directory,
                "fixtures.csv",
                FIXTURES,
            )
            fixture_preview = self.preview_service.preview(
                folder=Path(fixture_directory),
                provider="manual-research",
            )
            self.bridge.commit(
                db=self.db,
                preview=fixture_preview,
            )

        match = self.db.query(Match).one()
        prediction = Prediction(
            player_a="Player A",
            player_b="Player B",
            predicted_winner="Player A",
        )
        self.db.add(prediction)
        self.db.flush()

        trade = PaperTrade(
            prediction_id=prediction.id,
            fixture_id=match.id,
            market="Match Winner",
            selection="Player A",
            odds=2.5,
            stake=10.0,
            status="OPEN",
        )
        self.db.add(trade)
        self.db.commit()
        trade_id = trade.id

        with tempfile.TemporaryDirectory() as result_directory:
            result_preview = self.build_preview(
                result_directory,
                include_fixtures=False,
            )
            self.bridge.commit(
                db=self.db,
                preview=result_preview,
            )

        self.db.expire_all()
        settled = self.db.get(PaperTrade, trade_id)

        self.assertEqual(settled.fixture_id, match.id)
        self.assertEqual(settled.status, "WON")
        self.assertEqual(settled.profit_loss, 15.0)
        self.assertIsNotNone(settled.settled_at)

    def test_result_leaves_unsupported_linked_market_open(self):
        with tempfile.TemporaryDirectory() as fixture_directory:
            self.write_file(
                fixture_directory,
                "fixtures.csv",
                FIXTURES,
            )
            fixture_preview = self.preview_service.preview(
                folder=Path(fixture_directory),
                provider="manual-research",
            )
            self.bridge.commit(
                db=self.db,
                preview=fixture_preview,
            )

        match = self.db.query(Match).one()
        prediction = Prediction(
            player_a="Player A",
            player_b="Player B",
            predicted_winner="Player A",
        )
        self.db.add(prediction)
        self.db.flush()

        trade = PaperTrade(
            prediction_id=prediction.id,
            fixture_id=match.id,
            market="Most 180s",
            selection="Player A",
            odds=2.0,
            stake=10.0,
            status="OPEN",
        )
        self.db.add(trade)
        self.db.commit()
        trade_id = trade.id

        with tempfile.TemporaryDirectory() as result_directory:
            result_preview = self.build_preview(
                result_directory,
                include_fixtures=False,
            )
            self.bridge.commit(
                db=self.db,
                preview=result_preview,
            )

        self.db.expire_all()
        unchanged = self.db.get(PaperTrade, trade_id)

        self.assertEqual(unchanged.fixture_id, match.id)
        self.assertEqual(unchanged.status, "OPEN")
        self.assertIsNone(unchanged.profit_loss)
        self.assertIsNone(unchanged.settled_at)


    def test_result_does_not_create_duplicate_match(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(directory)

            self.bridge.commit(
                db=self.db,
                preview=preview,
            )

        self.assertEqual(self.db.query(Match).count(), 1)

    def test_result_creates_raw_record_and_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(directory)

            self.bridge.commit(
                db=self.db,
                preview=preview,
            )

        raw_results = (
            self.db.query(RawIngestionRecord)
            .filter_by(entity_type="result")
            .all()
        )

        self.assertEqual(len(raw_results), 1)
        self.assertEqual(raw_results[0].external_id, "match-1")
        self.assertTrue(raw_results[0].processed)

        mapping = (
            self.db.query(ProviderEntityMapping)
            .filter_by(
                provider="manual-research",
                entity_type="result",
                external_id="match-1",
            )
            .one()
        )

        self.assertEqual(
            mapping.internal_id,
            self.db.query(Match).one().id,
        )

    def test_result_records_field_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(directory)

            self.bridge.commit(
                db=self.db,
                preview=preview,
            )

        fields = {
            row.field_name
            for row in (
                self.db.query(DataProvenance)
                .filter_by(entity_type="result")
                .all()
            )
        }

        self.assertEqual(
            fields,
            {
                "status",
                "winner",
                "score",
                "first_leg_winner",
                "first_180_player",
            },
        )

    def test_result_is_tracked_as_updated_import_item(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(directory)

            self.bridge.commit(
                db=self.db,
                preview=preview,
            )

        item = (
            self.db.query(HistoricalImportItem)
            .filter_by(entity_type="result")
            .one()
        )

        self.assertEqual(item.action, "updated")
        self.assertEqual(item.external_id, "match-1")
        self.assertFalse(item.created_by_batch)
        self.assertIn('"previous"', item.detail)
        self.assertIn('"current"', item.detail)

    def test_identical_result_is_duplicate_safe(self):
        with tempfile.TemporaryDirectory() as first_directory:
            first_preview = self.build_preview(first_directory)

            self.bridge.commit(
                db=self.db,
                preview=first_preview,
            )

        with tempfile.TemporaryDirectory() as second_directory:
            second_preview = self.build_preview(
                second_directory,
                include_fixtures=False,
            )

            second_report = self.bridge.commit(
                db=self.db,
                preview=second_preview,
            )

        self.assertEqual(self.db.query(Match).count(), 1)

        duplicate_item = (
            self.db.query(HistoricalImportItem)
            .filter_by(
                batch_id=second_report.batch_id,
                entity_type="result",
                action="duplicate",
            )
            .one()
        )

        self.assertEqual(
            duplicate_item.external_id,
            "match-1",
        )

    def test_result_without_existing_fixture_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            preview = self.build_preview(
                directory,
                include_fixtures=False,
            )

            report = self.bridge.commit(
                db=self.db,
                preview=preview,
            )

        self.assertEqual(self.db.query(Match).count(), 0)
        self.assertEqual(report.rejected_rows, 1)

        rejected = (
            self.db.query(HistoricalImportItem)
            .filter_by(
                batch_id=report.batch_id,
                entity_type="result",
                action="rejected",
            )
            .one()
        )

        self.assertIn(
            "No existing fixture mapping",
            rejected.detail,
        )

    def test_result_only_commit_creates_batch(self):
        with tempfile.TemporaryDirectory() as fixture_directory:
            fixture_preview = self.preview_service.preview(
                folder=Path(fixture_directory),
                provider="manual-research",
            )

            self.write_file(
                fixture_directory,
                "fixtures.csv",
                FIXTURES,
            )

            fixture_preview = self.preview_service.preview(
                folder=Path(fixture_directory),
                provider="manual-research",
            )

            self.bridge.commit(
                db=self.db,
                preview=fixture_preview,
            )

        with tempfile.TemporaryDirectory() as result_directory:
            result_preview = self.build_preview(
                result_directory,
                include_fixtures=False,
            )

            report = self.bridge.commit(
                db=self.db,
                preview=result_preview,
                filename="modus-results.csv",
            )

        batch = (
            self.db.query(HistoricalImportBatch)
            .filter_by(id=report.batch_id)
            .one()
        )

        self.assertEqual(batch.filename, "modus-results.csv")
        self.assertEqual(batch.received_rows, 1)
        self.assertEqual(batch.status, "imported")
        self.assertEqual(report.entity_counts["fixtures"], 0)
        self.assertEqual(report.entity_counts["results"], 1)


if __name__ == "__main__":
    unittest.main()