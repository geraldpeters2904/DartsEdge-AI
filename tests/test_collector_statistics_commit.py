import tempfile
import unittest
from pathlib import Path

from app.collector.commit_bridge import (
    CollectorCommitBridge,
)
from app.collector.folder_preview import (
    CollectorFolderPreviewService,
)
from app.models.historical_import import (
    HistoricalImportItem,
)
from app.models.player_match_performance import (
    PlayerMatchPerformance,
)
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

RESULTS = (
    "match_external_id,player_a_external_id,"
    "player_b_external_id,winner_external_id,"
    "player_a_legs,player_b_legs\n"
    "match-1,player-a,player-b,player-a,4,2\n"
)

STATISTICS = (
    "match_external_id,player_external_id,"
    "three_dart_average,first_nine_average,"
    "scores_100_plus,scores_140_plus,scores_180,"
    "checkout_attempts,checkouts_completed,"
    "checkout_percentage,highest_checkout,"
    "legs_won,legs_lost,match_duration_seconds\n"
    "match-1,player-a,94.25,101.5,12,6,2,"
    "10,4,40.0,121,4,2,1680\n"
    "match-1,player-b,90.10,96.4,10,5,1,"
    "8,2,25.0,80,2,4,1680\n"
)


class CollectorStatisticsCommitTests(unittest.TestCase):
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
        include_results=True,
        statistics=STATISTICS,
    ):
        if include_fixtures:
            self.write_file(
                directory,
                "fixtures.csv",
                FIXTURES,
            )

        if include_results:
            self.write_file(
                directory,
                "results.csv",
                RESULTS,
            )

        self.write_file(
            directory,
            "statistics.csv",
            statistics,
        )

        return self.preview_service.preview(
            folder=Path(directory),
            provider="manual-research",
        )

    def test_statistics_create_two_performances(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self.bridge.commit(
                db=self.db,
                preview=self.build_preview(directory),
            )

        rows = (
            self.db.query(PlayerMatchPerformance)
            .order_by(
                PlayerMatchPerformance.player_external_id
            )
            .all()
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            report.entity_counts["statistics"],
            2,
        )
        self.assertEqual(
            rows[0].three_dart_average,
            94.25,
        )
        self.assertEqual(rows[0].scores_180, 2)
        self.assertTrue(rows[0].won_match)
        self.assertFalse(rows[1].won_match)

    def test_unknown_and_zero_remain_distinct(self):
        statistics = (
            "match_external_id,player_external_id,"
            "scores_180,checkout_attempts,"
            "checkouts_completed\n"
            "match-1,player-a,,0,0\n"
        )

        with tempfile.TemporaryDirectory() as directory:
            report = self.bridge.commit(
                db=self.db,
                preview=self.build_preview(
                    directory,
                    include_results=False,
                    statistics=statistics,
                ),
            )

        row = self.db.query(
            PlayerMatchPerformance
        ).one()

        self.assertIsNone(row.scores_180)
        self.assertEqual(row.checkout_attempts, 0)
        self.assertEqual(row.checkouts_completed, 0)
        self.assertEqual(report.rejected_rows, 0)

    def test_identical_statistics_are_duplicate_safe(self):
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
                    include_results=False,
                ),
            )

        self.assertEqual(
            self.db.query(
                PlayerMatchPerformance
            ).count(),
            2,
        )

        duplicates = (
            self.db.query(HistoricalImportItem)
            .filter_by(
                batch_id=report.batch_id,
                entity_type=(
                    "player_match_performance"
                ),
                action="duplicate",
            )
            .count()
        )

        self.assertEqual(duplicates, 2)

    def test_statistics_without_fixture_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self.bridge.commit(
                db=self.db,
                preview=self.build_preview(
                    directory,
                    include_fixtures=False,
                    include_results=False,
                ),
            )

        self.assertEqual(
            self.db.query(
                PlayerMatchPerformance
            ).count(),
            0,
        )
        self.assertEqual(report.rejected_rows, 2)

    def test_conflicting_statistics_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            self.bridge.commit(
                db=self.db,
                preview=self.build_preview(directory),
            )

        changed = STATISTICS.replace(
            "94.25",
            "99.99",
            1,
        )

        with tempfile.TemporaryDirectory() as directory:
            report = self.bridge.commit(
                db=self.db,
                preview=self.build_preview(
                    directory,
                    include_fixtures=False,
                    include_results=False,
                    statistics=changed,
                ),
            )

        player_a = (
            self.db.query(PlayerMatchPerformance)
            .filter_by(
                player_external_id="player-a"
            )
            .one()
        )

        self.assertEqual(
            player_a.three_dart_average,
            94.25,
        )
        self.assertEqual(report.rejected_rows, 1)

    def test_rollback_removes_created_performances(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self.bridge.commit(
                db=self.db,
                preview=self.build_preview(directory),
            )

        self.assertEqual(
            self.db.query(
                PlayerMatchPerformance
            ).count(),
            2,
        )

        rollback_batch(
            self.db,
            report.batch_id,
        )

        self.assertEqual(
            self.db.query(
                PlayerMatchPerformance
            ).count(),
            0,
        )


if __name__ == "__main__":
    unittest.main()
