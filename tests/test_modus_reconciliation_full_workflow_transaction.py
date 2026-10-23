import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.collector.commit_bridge import CollectorCommitBridge
from app.collector.folder_preview import CollectorFolderPreviewService
from app.models.canonical_data import ProviderEntityMapping
from app.models.match import Match
from app.models.paper_trade import PaperTrade
from app.models.player_career_profile import PlayerCareerProfile
from app.models.player_match_performance import PlayerMatchPerformance
from app.services.current_match_enrichment_workflow_service import (
    CurrentMatchEnrichmentWorkflowService,
)
from app.services.modus_reconciliation_plan_execution_service import (
    execute_modus_reconciliation_mappings,
)
from tests.helpers.database import create_test_session
from tests.test_current_match_enrichment_persistence_service import (
    FIXTURES,
    statistics_result,
)


class FakeDetailService:
    def fetch(self, candidate, *, timeout_seconds):
        if candidate.resolved_modus_match_id != 19001:
            raise ValueError("Unexpected MODUS match ID.")

        return type("Detail", (), {"status": "validated"})()


class FakeStatisticsService:
    def build(self, detail):
        return statistics_result()


class ModusReconciliationFullWorkflowTransactionTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixtures.csv"
            path.write_text(FIXTURES, encoding="utf-8")
            preview = CollectorFolderPreviewService().preview(
                folder=Path(directory),
                provider="modus-official",
            )
            CollectorCommitBridge().commit(db=self.db, preview=preview)

        mapping = (
            self.db.query(ProviderEntityMapping)
            .filter_by(
                provider="modus-official",
                entity_type="fixture",
                external_id="modus-match-19001",
            )
            .one()
        )
        self.match_id = mapping.internal_id

        match = self.db.get(Match, self.match_id)
        match.status = "scheduled"
        match.score = None
        match.winner = None
        match.first_leg_winner = None
        match.first_180_player = None
        mapping.external_id = "modus-match-74325001"
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_full_enrichment_is_reversible_by_outer_rollback(self):
        workflow = CurrentMatchEnrichmentWorkflowService(
            detail_service=FakeDetailService(),
            statistics_service=FakeStatisticsService(),
        )

        self.db.connection().exec_driver_sql("BEGIN")

        report = execute_modus_reconciliation_mappings(
            self.db,
            mappings=((self.match_id, 19001),),
            workflow_service=workflow,
        )

        self.assertEqual(report.completed, 1)
        self.assertEqual(report.failed, 0)
        self.assertTrue(self.db.in_transaction())

        match = self.db.get(Match, self.match_id)
        self.assertEqual(match.status, "completed")
        self.assertEqual(match.score, "4-2")
        self.assertEqual(match.winner, "Player A")

        mapping = (
            self.db.query(ProviderEntityMapping)
            .filter_by(
                provider="modus-official",
                entity_type="fixture",
                internal_id=self.match_id,
            )
            .one()
        )
        self.assertEqual(mapping.external_id, "modus-match-19001")
        self.assertEqual(
            self.db.query(PlayerMatchPerformance)
            .filter_by(match_id=self.match_id)
            .count(),
            2,
        )
        self.assertEqual(
            self.db.query(PlayerCareerProfile).count(),
            2,
        )

        self.db.rollback()
        self.db.expire_all()

        match = self.db.get(Match, self.match_id)
        self.assertEqual(match.status, "scheduled")
        self.assertIsNone(match.score)
        self.assertIsNone(match.winner)

        mapping = (
            self.db.query(ProviderEntityMapping)
            .filter_by(
                provider="modus-official",
                entity_type="fixture",
                internal_id=self.match_id,
            )
            .one()
        )
        self.assertEqual(mapping.external_id, "modus-match-74325001")
        self.assertEqual(
            self.db.query(PlayerMatchPerformance).count(),
            0,
        )
        self.assertEqual(
            self.db.query(PlayerCareerProfile).count(),
            0,
        )


    def test_profile_refresh_failure_rolls_back_entire_fixture(self):
        class FailingProfileRefreshService:
            def refresh(self, db, *, internal_match_id):
                assert db.query(PlayerMatchPerformance).filter_by(
                    match_id=internal_match_id
                ).count() == 2
                raise RuntimeError("Simulated career-profile refresh failure")

        workflow = CurrentMatchEnrichmentWorkflowService(
            detail_service=FakeDetailService(),
            statistics_service=FakeStatisticsService(),
            profile_refresh_service=FailingProfileRefreshService(),
        )

        self.db.connection().exec_driver_sql("BEGIN")

        report = execute_modus_reconciliation_mappings(
            self.db,
            mappings=((self.match_id, 19001),),
            workflow_service=workflow,
        )

        self.assertEqual(report.attempted, 1)
        self.assertEqual(report.completed, 0)
        self.assertEqual(report.failed, 1)
        self.assertEqual(report.failed_fixture_ids, (self.match_id,))
        self.assertTrue(self.db.in_transaction())

        self.db.expire_all()

        match = self.db.get(Match, self.match_id)
        self.assertEqual(match.status, "scheduled")
        self.assertIsNone(match.score)
        self.assertIsNone(match.winner)

        mapping = (
            self.db.query(ProviderEntityMapping)
            .filter_by(
                provider="modus-official",
                entity_type="fixture",
                internal_id=self.match_id,
            )
            .one()
        )
        self.assertEqual(mapping.external_id, "modus-match-74325001")

        self.assertEqual(
            self.db.query(PlayerMatchPerformance)
            .filter_by(match_id=self.match_id)
            .count(),
            0,
        )
        self.assertEqual(
            self.db.query(PlayerCareerProfile).count(),
            0,
        )

        self.db.rollback()


    def test_profile_refresh_failure_reverses_paper_trade_settlement(self):
        trade = PaperTrade(
            fixture_id=self.match_id,
            market="Match Winner",
            selection="Player A",
            bookmaker="Test",
            odds=2.5,
            stake=10.0,
            status="OPEN",
        )
        self.db.add(trade)
        self.db.commit()
        trade_id = trade.id

        class FailingProfileRefreshService:
            def refresh(self, db, *, internal_match_id):
                settled = db.get(PaperTrade, trade_id)
                assert settled.status != "OPEN", (
                    "Trade must actually settle before the injected failure."
                )
                assert settled.profit_loss == 15.0
                assert settled.settled_at is not None
                raise RuntimeError("Simulated failure after Paper Trade settlement")

        workflow = CurrentMatchEnrichmentWorkflowService(
            detail_service=FakeDetailService(),
            statistics_service=FakeStatisticsService(),
            profile_refresh_service=FailingProfileRefreshService(),
        )

        self.db.connection().exec_driver_sql("BEGIN")

        report = execute_modus_reconciliation_mappings(
            self.db,
            mappings=((self.match_id, 19001),),
            workflow_service=workflow,
        )

        self.assertEqual(report.attempted, 1)
        self.assertEqual(report.completed, 0)
        self.assertEqual(report.failed, 1)
        self.assertEqual(report.failed_fixture_ids, (self.match_id,))

        self.db.expire_all()
        restored = self.db.get(PaperTrade, trade_id)
        self.assertEqual(restored.status, "OPEN")
        self.assertIsNone(restored.profit_loss)
        self.assertIsNone(restored.settled_at)

        match = self.db.get(Match, self.match_id)
        self.assertEqual(match.status, "scheduled")
        self.assertIsNone(match.score)
        self.assertIsNone(match.winner)

        self.db.rollback()


if __name__ == "__main__":
    unittest.main()
