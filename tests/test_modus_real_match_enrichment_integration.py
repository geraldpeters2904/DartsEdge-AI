import tempfile
import unittest

from datetime import datetime
from pathlib import Path

from app.collector.commit_bridge import CollectorCommitBridge
from app.collector.folder_preview import CollectorFolderPreviewService
from app.models.match import Match
from app.models.player_match_performance import PlayerMatchPerformance
from app.providers.adapters.modus_official.real_match_parser import (
    ModusRealMatchPageParser,
)
from app.services.current_match_enrichment_detail_service import (
    CurrentMatchEnrichmentDetailResult,
)
from app.services.current_match_enrichment_statistics_service import (
    CurrentMatchEnrichmentStatisticsService,
)
from app.services.current_match_enrichment_persistence_service import (
    CurrentMatchEnrichmentPersistenceService,
)
from tests.helpers.database import create_test_session


FIXTURE = Path(
    "tests/fixtures/modus/match_18195_real.html"
)


class ModusRealMatchEnrichmentIntegrationTests(unittest.TestCase):

    def setUp(self):
        self.db = create_test_session()

    def tearDown(self):
        self.db.close()

    def test_real_modus_match_flows_to_canonical_persistence(self):
        html = FIXTURE.read_text(encoding="utf-8")

        parser = ModusRealMatchPageParser()
        parsed = parser.parse(
            html,
            match_id=18195,
        )

        detail_result = CurrentMatchEnrichmentDetailResult(
            internal_match_id=1,
            modus_match_id=18195,
            source_url="https://www.modus-super-series.com/match-db-stats.php?match_id=18195",
            player_a=parsed.player_a_name,
            player_b=parsed.player_b_name,
            player_a_legs=parsed.player_a_legs,
            player_b_legs=parsed.player_b_legs,
            detail=parsed,
            status="validated",
            message="Validated real MODUS fixture.",
        )

        statistics_service = (
            CurrentMatchEnrichmentStatisticsService()
        )

        canonical = statistics_service.build(
            detail_result,
            retrieved_at=datetime(
                2026,
                7,
                20,
                10,
                0,
            ),
        )

        self.assertEqual(
            canonical.status,
            "canonicalized",
        )

        self.assertIsNotNone(canonical.result)

        result = canonical.result

        self.assertEqual(
            result.player_a_legs,
            4,
        )
        self.assertEqual(
            result.player_b_legs,
            2,
        )
        self.assertEqual(
            result.winner_external_id,
            "modus-player-derek-coulson",
        )

        stats = canonical.statistics

        self.assertEqual(len(stats), 2)

        self.assertEqual(
            stats[0].player_external_id,
            "modus-player-derek-coulson",
        )
        self.assertEqual(
            stats[0].three_dart_average,
            108.70,
        )
        self.assertEqual(
            stats[0].scores_180,
            3,
        )
        self.assertEqual(
            stats[0].checkouts_completed,
            4,
        )
        self.assertEqual(
            stats[0].checkout_attempts,
            8,
        )

        self.assertEqual(
            stats[1].player_external_id,
            "modus-player-david-evans",
        )
        self.assertEqual(
            stats[1].three_dart_average,
            85.56,
        )
        self.assertEqual(
            stats[1].scores_180,
            0,
        )
        self.assertEqual(
            stats[1].checkouts_completed,
            2,
        )
        self.assertEqual(
            stats[1].checkout_attempts,
            3,
        )

        # Create the canonical warehouse match that the persistence
        # service expects to already exist.

        match = Match(
            date=parsed.played_at.date(),
            tournament="MODUS Super Series",
            stage=parsed.group,
            match_format="Best of 7",
            status="completed",
            player_a=parsed.player_a_name,
            player_b=parsed.player_b_name,
            winner=parsed.player_a_name,
            score="4-2",
        )
        self.db.add(match)
        self.db.flush()

        canonical = canonical.__class__(
            internal_match_id=match.id,
            modus_match_id=canonical.modus_match_id,
            match_external_id=canonical.match_external_id,
            statistics=canonical.statistics,
            status=canonical.status,
            message=canonical.message,
            result=canonical.result,
        )

        # Establish the canonical warehouse mappings required by the
        # immutable result/statistics committers.
        #
        # This mirrors the canonical mapping state created by the
        # production Collector path without requiring a complete CSV
        # folder for this focused integration test.

        from app.models.canonical_data import ProviderEntityMapping
        from app.models.player import Player
        from app.collector.commit_helpers import map_player_external_id

        self.db.add(
            ProviderEntityMapping(
                provider="modus-official",
                entity_type="fixture",
                external_id="modus-match-18195",
                internal_id=match.id,
                competition_code="MODUS",
            )
        )

        derek_player = Player(name="Derek Coulson")
        david_player = Player(name="David Evans")

        self.db.add(derek_player)
        self.db.add(david_player)
        self.db.flush()

        map_player_external_id(
            db=self.db,
            provider="modus-official",
            external_id="modus-player-derek-coulson",
            player_name="Derek Coulson",
            competition_code="MODUS",
        )

        map_player_external_id(
            db=self.db,
            provider="modus-official",
            external_id="modus-player-david-evans",
            player_name="David Evans",
            competition_code="MODUS",
        )

        self.db.commit()

        persistence = (
            CurrentMatchEnrichmentPersistenceService()
        )

        persisted = persistence.persist(
            self.db,
            canonical,
        )

        self.assertEqual(
            persisted.status,
            "persisted",
        )
        self.assertEqual(
            persisted.rejected_rows,
            0,
        )

        rows = (
            self.db.query(PlayerMatchPerformance)
            .order_by(
                PlayerMatchPerformance.player_external_id
            )
            .all()
        )

        self.assertEqual(
            len(rows),
            2,
        )

        derek = next(
            row
            for row in rows
            if row.player_external_id
            == "modus-player-derek-coulson"
        )
        david = next(
            row
            for row in rows
            if row.player_external_id
            == "modus-player-david-evans"
        )

        self.assertEqual(
            derek.three_dart_average,
            108.70,
        )
        self.assertEqual(
            derek.scores_180,
            3,
        )
        self.assertEqual(
            derek.checkouts_completed,
            4,
        )

        self.assertEqual(
            david.three_dart_average,
            85.56,
        )
        self.assertEqual(
            david.scores_180,
            0,
        )
        self.assertEqual(
            david.checkouts_completed,
            2,
        )


if __name__ == "__main__":
    unittest.main()
