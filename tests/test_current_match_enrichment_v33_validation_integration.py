import unittest
from datetime import date, timedelta

from app.models.match import Match
from app.models.player import Player
from app.models.player_match_performance import (
    PlayerMatchPerformance,
)
from app.services.current_match_enrichment_v33_validation_service import (
    CurrentMatchEnrichmentV33ValidationService,
)
from tests.helpers.database import create_test_session


class CurrentMatchEnrichmentV33ValidationIntegrationTests(
    unittest.TestCase
):
    def setUp(self):
        self.db = create_test_session()

        self.player_a = Player(
            name="Validation Strong Player",
            elo=1500.0,
        )
        self.player_b = Player(
            name="Validation Weak Player",
            elo=1500.0,
        )

        self.db.add_all([
            self.player_a,
            self.player_b,
        ])
        self.db.flush()

        self._seed_history()

        self.target = Match(
            date=date(2026, 8, 1),
            tournament="MODUS Super Series",
            stage="Group A",
            status="completed",
            player_a=self.player_a.name,
            player_b=self.player_b.name,
            winner=self.player_a.name,
            score="4-1",
        )

        self.db.add(self.target)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _seed_history(self):
        start = date(2026, 7, 1)

        for index in range(5):
            opponent_a = Player(
                name=f"Validation A Opponent {index}",
                elo=1500.0,
            )
            opponent_b = Player(
                name=f"Validation B Opponent {index}",
                elo=1500.0,
            )

            self.db.add_all([
                opponent_a,
                opponent_b,
            ])
            self.db.flush()

            match_date = (
                start
                + timedelta(days=index)
            )

            match_a = Match(
                date=match_date,
                tournament="MODUS Super Series",
                stage="Group A",
                status="completed",
                player_a=self.player_a.name,
                player_b=opponent_a.name,
                winner=self.player_a.name,
                score="4-1",
            )

            match_b = Match(
                date=match_date,
                tournament="MODUS Super Series",
                stage="Group A",
                status="completed",
                player_a=self.player_b.name,
                player_b=opponent_b.name,
                winner=opponent_b.name,
                score="1-4",
            )

            self.db.add_all([
                match_a,
                match_b,
            ])
            self.db.flush()

            self.db.add_all([
                PlayerMatchPerformance(
                    match_id=match_a.id,
                    player_id=self.player_a.id,
                    opponent_id=opponent_a.id,
                    competition_code="MODUS",
                    player_external_id=(
                        "modus-player-validation-strong"
                    ),
                    won_match=True,
                    legs_won=4,
                    legs_lost=1,
                    three_dart_average=99.0,
                    first_nine_average=105.0,
                    scores_100_plus=12,
                    scores_140_plus=7,
                    scores_180=3,
                    checkout_attempts=8,
                    checkouts_completed=4,
                    checkout_percentage=50.0,
                    highest_checkout=120,
                    source_provider="modus-official",
                    source_external_id=(
                        f"modus:statistics:strong:{index}"
                    ),
                    source_confidence="verified",
                ),
                PlayerMatchPerformance(
                    match_id=match_b.id,
                    player_id=self.player_b.id,
                    opponent_id=opponent_b.id,
                    competition_code="MODUS",
                    player_external_id=(
                        "modus-player-validation-weak"
                    ),
                    won_match=False,
                    legs_won=1,
                    legs_lost=4,
                    three_dart_average=82.0,
                    first_nine_average=87.0,
                    scores_100_plus=5,
                    scores_140_plus=2,
                    scores_180=0,
                    checkout_attempts=8,
                    checkouts_completed=2,
                    checkout_percentage=25.0,
                    highest_checkout=60,
                    source_provider="modus-official",
                    source_external_id=(
                        f"modus:statistics:weak:{index}"
                    ),
                    source_confidence="verified",
                ),
            ])

        self.db.flush()

    def test_v33_historical_validation_reports_probability_quality(
        self,
    ):
        # Ten completed history matches were inserted before
        # the target match, so offset 10 selects only the target.
        result = (
            CurrentMatchEnrichmentV33ValidationService()
            .validate(
                self.db,
                offset=10,
                limit=1,
                competition_code="MODUS",
            )
        )

        self.assertEqual(
            result.model_version,
            "transparent-v3.3",
        )

        self.assertEqual(
            result.match_ids,
            (self.target.id,),
        )

        self.assertEqual(
            result.matches_considered,
            1,
        )

        self.assertEqual(
            result.matches_evaluated,
            1,
        )

        self.assertEqual(
            result.matches_skipped,
            0,
        )

        self.assertEqual(
            result.correct_predictions,
            1,
        )

        self.assertEqual(
            result.accuracy,
            100.0,
        )

        self.assertIsNotNone(
            result.average_brier_score,
        )

        self.assertIsNotNone(
            result.average_log_loss,
        )

        # A useful prediction should beat an uninformed 50/50
        # forecast on both proper probability-scoring measures.
        self.assertLess(
            result.average_brier_score,
            0.25,
        )

        self.assertLess(
            result.average_log_loss,
            0.6932,
        )


if __name__ == "__main__":
    unittest.main()
