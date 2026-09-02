import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.collector.commit_bridge import CollectorCommitBridge
from app.collector.folder_preview import CollectorFolderPreviewService
from app.models.historical_import import HistoricalImportBatch
from app.models.paper_trade import PaperTrade
from app.models.prediction import Prediction
from app.collector.commit_helpers import find_match_by_external_id
from app.models.player_match_performance import PlayerMatchPerformance
from app.schemas.canonical import (
    CanonicalMatchResult,
    CanonicalPlayerMatchStatistics,
    CompetitionCode,
    RecordConfidence,
    SourceReference,
)
from app.services.current_match_enrichment_persistence_service import (
    CurrentMatchEnrichmentPersistenceService,
)
from app.services.current_match_enrichment_statistics_service import (
    CurrentMatchEnrichmentStatisticsResult,
)
from tests.helpers.database import create_test_session


FIXTURES = (
    "external_id,competition_code,competition_name,"
    "scheduled_at,status,match_format,"
    "player_a_external_id,player_a_name,"
    "player_b_external_id,player_b_name\n"
    "modus-match-19001,MODUS,MODUS Super Series,"
    "2026-08-01T10:00:00,completed,Best of 7,"
    "modus-player-player-a,Player A,"
    "modus-player-player-b,Player B\n"
)


def source(player_external_id):
    return SourceReference(
        provider="modus-official",
        external_id=(
            "modus:statistics:19001:"
            f"{player_external_id}"
        ),
        retrieved_at=datetime(
            2026,
            8,
            10,
            7,
            30,
        ),
        competition_code=CompetitionCode.MODUS,
        confidence=RecordConfidence.VERIFIED,
    )


def result_source():
    return SourceReference(
        provider="modus-official",
        external_id="modus:result:19001",
        retrieved_at=datetime(
            2026,
            8,
            10,
            7,
            30,
        ),
        competition_code=CompetitionCode.MODUS,
        confidence=RecordConfidence.VERIFIED,
    )


def canonical_result():
    return CanonicalMatchResult(
        match_external_id="modus-match-19001",
        player_a_external_id="modus-player-player-a",
        player_b_external_id="modus-player-player-b",
        winner_external_id="modus-player-player-a",
        player_a_legs=4,
        player_b_legs=2,
        completed_at=datetime(
            2026,
            8,
            1,
            10,
            20,
        ),
        source=result_source(),
    )


def statistics_result(
    *,
    player_a_average=92.5,
):
    first = CanonicalPlayerMatchStatistics(
        match_external_id="modus-match-19001",
        player_external_id="modus-player-player-a",
        three_dart_average=player_a_average,
        scores_100_plus=11,
        scores_140_plus=6,
        scores_180=2,
        checkout_attempts=8,
        checkouts_completed=4,
        checkout_percentage=50.0,
        highest_checkout=121,
        legs_won=4,
        legs_lost=2,
        source=source(
            "modus-player-player-a"
        ),
    )

    second = CanonicalPlayerMatchStatistics(
        match_external_id="modus-match-19001",
        player_external_id="modus-player-player-b",
        three_dart_average=88.1,
        scores_100_plus=9,
        scores_140_plus=5,
        scores_180=1,
        checkout_attempts=6,
        checkouts_completed=2,
        checkout_percentage=33.333,
        highest_checkout=96,
        legs_won=2,
        legs_lost=4,
        source=source(
            "modus-player-player-b"
        ),
    )

    return CurrentMatchEnrichmentStatisticsResult(
        internal_match_id=101,
        modus_match_id=19001,
        match_external_id="modus-match-19001",
        statistics=(
            first,
            second,
        ),
        status="canonicalized",
        message="Canonicalized.",
        result=canonical_result(),
    )


class CurrentMatchEnrichmentPersistenceServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.db = create_test_session()
        self.preview_service = (
            CollectorFolderPreviewService()
        )
        self.bridge = CollectorCommitBridge()
        self.service = (
            CurrentMatchEnrichmentPersistenceService()
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixtures.csv"
            path.write_text(
                FIXTURES,
                encoding="utf-8",
            )

            preview = self.preview_service.preview(
                folder=Path(directory),
                provider="modus-official",
            )

            self.bridge.commit(
                db=self.db,
                preview=preview,
            )

    def tearDown(self):
        self.db.close()

    def test_persists_two_performance_rows(self):
        result = self.service.persist(
            self.db,
            statistics_result(),
        )

        self.assertEqual(
            result.status,
            "persisted",
        )
        self.assertEqual(
            result.received_rows,
            3,
        )
        self.assertEqual(
            result.rejected_rows,
            0,
        )

        rows = (
            self.db.query(
                PlayerMatchPerformance
            )
            .order_by(
                PlayerMatchPerformance
                .player_external_id
            )
            .all()
        )

        self.assertEqual(
            len(rows),
            2,
        )
        self.assertEqual(
            rows[0].three_dart_average,
            92.5,
        )
        self.assertEqual(
            rows[1].three_dart_average,
            88.1,
        )

        batch = (
            self.db.query(
                HistoricalImportBatch
            )
            .filter(
                HistoricalImportBatch.id
                == result.batch_id
            )
            .one()
        )

        self.assertEqual(
            batch.provider,
            "modus-official",
        )
        self.assertEqual(
            batch.competition_code,
            "MODUS",
        )
        self.assertEqual(
            batch.status,
            "imported",
        )

    def test_persist_settles_linked_match_winner_trade(self):
        match = find_match_by_external_id(
            db=self.db,
            provider="modus-official",
            match_external_id="modus-match-19001",
        )
        self.assertIsNotNone(match)
        self.assertNotEqual(match.id, 101)

        prediction = Prediction(
            player_a="Player A",
            player_b="Player B",
            predicted_winner="Player A",
            win_prob_a=0.60,
            win_prob_b=0.40,
            confidence=2,
            rating_a=0,
            rating_b=0,
            first_180_a=0,
            first_180_b=0,
        )
        self.db.add(prediction)
        self.db.flush()

        trade = PaperTrade(
            prediction_id=prediction.id,
            fixture_id=match.id,
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

        self.service.persist(
            self.db,
            statistics_result(),
        )

        self.db.expire_all()
        settled = self.db.get(PaperTrade, trade_id)

        self.assertEqual(settled.fixture_id, match.id)
        self.assertEqual(settled.status, "WON")
        self.assertEqual(settled.profit_loss, 15.0)
        self.assertIsNotNone(settled.settled_at)

    def test_identical_rerun_is_duplicate_safe(self):
        self.service.persist(
            self.db,
            statistics_result(),
        )

        second = self.service.persist(
            self.db,
            statistics_result(),
        )

        self.assertEqual(
            second.status,
            "persisted",
        )
        self.assertEqual(
            second.rejected_rows,
            0,
        )
        self.assertEqual(
            self.db.query(
                PlayerMatchPerformance
            ).count(),
            2,
        )

    def test_conflicting_rerun_does_not_overwrite(self):
        self.service.persist(
            self.db,
            statistics_result(),
        )

        with self.assertRaisesRegex(
            ValueError,
            "rejected 1 canonical record",
        ):
            self.service.persist(
                self.db,
                statistics_result(
                    player_a_average=99.9,
                ),
            )

        rows = (
            self.db.query(
                PlayerMatchPerformance
            )
            .order_by(
                PlayerMatchPerformance
                .player_external_id
            )
            .all()
        )

        self.assertEqual(
            len(rows),
            2,
        )
        self.assertEqual(
            rows[0].three_dart_average,
            92.5,
        )

    def test_failed_persist_rolls_back_paper_trade_settlement(self):
        self.service.persist(
            self.db,
            statistics_result(),
        )

        match = find_match_by_external_id(
            db=self.db,
            provider="modus-official",
            match_external_id="modus-match-19001",
        )
        self.assertIsNotNone(match)

        prediction = Prediction(
            player_a="Player A",
            player_b="Player B",
            predicted_winner="Player A",
            win_prob_a=0.60,
            win_prob_b=0.40,
            confidence=2,
            rating_a=0,
            rating_b=0,
            first_180_a=0,
            first_180_b=0,
        )
        self.db.add(prediction)
        self.db.flush()

        trade = PaperTrade(
            prediction_id=prediction.id,
            fixture_id=match.id,
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

        with self.assertRaisesRegex(
            ValueError,
            "rejected 1 canonical record",
        ):
            self.service.persist(
                self.db,
                statistics_result(
                    player_a_average=99.9,
                ),
            )

        self.db.expire_all()
        restored = self.db.get(
            PaperTrade,
            trade_id,
        )

        self.assertEqual(restored.status, "OPEN")
        self.assertIsNone(restored.profit_loss)
        self.assertIsNone(restored.settled_at)

    def test_noncanonical_result_is_rejected(self):
        result = statistics_result()

        invalid = (
            CurrentMatchEnrichmentStatisticsResult(
                internal_match_id=(
                    result.internal_match_id
                ),
                modus_match_id=(
                    result.modus_match_id
                ),
                match_external_id=(
                    result.match_external_id
                ),
                statistics=result.statistics,
                status="error",
                message="Invalid.",
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "Only canonicalized",
        ):
            self.service.persist(
                self.db,
                invalid,
            )


if __name__ == "__main__":
    unittest.main()
