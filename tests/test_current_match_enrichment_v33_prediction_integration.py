import unittest
from datetime import date, timedelta

from app.models.match import Match
from app.models.player import Player
from app.models.player_match_performance import (
    PlayerMatchPerformance,
)
from app.services.advanced_prediction_input_builder import (
    AdvancedPredictionInputBuilder,
)
from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)
from tests.helpers.database import create_test_session


class CurrentMatchEnrichmentV33PredictionIntegrationTests(
    unittest.TestCase
):
    def setUp(self):
        self.db = create_test_session()

        self.player_a = Player(
            name="Enriched Strong Player",
            elo=1500.0,
            average=90.0,
            checkout=35.0,
        )
        self.player_b = Player(
            name="Enriched Weak Player",
            elo=1500.0,
            average=90.0,
            checkout=35.0,
        )

        self.db.add_all(
            [
                self.player_a,
                self.player_b,
            ]
        )
        self.db.flush()

        self._seed_history()

        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _seed_history(self):
        """
        Seed equal-sized MODUS histories.

        Player A deliberately receives stronger immutable
        performance observations than Player B.
        """
        start = date(2026, 7, 1)

        for index in range(10):
            match_date = start + timedelta(
                days=index
            )

            # Use separate historical matches so each player's
            # observed performance is independent and explicit.
            opponent_a = Player(
                name=f"A Opponent {index}",
                elo=1500.0,
            )
            opponent_b = Player(
                name=f"B Opponent {index}",
                elo=1500.0,
            )

            self.db.add_all(
                [
                    opponent_a,
                    opponent_b,
                ]
            )
            self.db.flush()

            match_a = Match(
                date=match_date,
                player_a=self.player_a.name,
                player_b=opponent_a.name,
                winner=self.player_a.name,
                score="4-1",
                status="completed",
            )
            match_b = Match(
                date=match_date,
                player_a=self.player_b.name,
                player_b=opponent_b.name,
                winner=opponent_b.name,
                score="2-4",
                status="completed",
            )

            self.db.add_all(
                [
                    match_a,
                    match_b,
                ]
            )
            self.db.flush()

            self.db.add(
                PlayerMatchPerformance(
                    match_id=match_a.id,
                    player_id=self.player_a.id,
                    opponent_id=opponent_a.id,
                    competition_code="MODUS",
                    player_external_id=(
                        "modus-player-enriched-strong-player"
                    ),
                    won_match=True,
                    legs_won=4,
                    legs_lost=1,
                    three_dart_average=98.0,
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
                        f"modus:statistics:a:{index}"
                    ),
                    source_confidence="verified",
                )
            )

            self.db.add(
                PlayerMatchPerformance(
                    match_id=match_b.id,
                    player_id=self.player_b.id,
                    opponent_id=opponent_b.id,
                    competition_code="MODUS",
                    player_external_id=(
                        "modus-player-enriched-weak-player"
                    ),
                    won_match=False,
                    legs_won=2,
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
                        f"modus:statistics:b:{index}"
                    ),
                    source_confidence="verified",
                )
            )

    def test_enriched_performance_changes_active_v33_prediction(
        self,
    ):
        snapshot = AdvancedPredictionInputBuilder().build(
            self.db,
            player_a=self.player_a,
            player_b=self.player_b,
            match_id=999001,
            competition_code="MODUS",
        )

        prediction = (
            TransparentPredictionEngineV33()
            .predict(snapshot)
        )

        self.assertEqual(
            prediction.model_version,
            "transparent-v3.3",
        )

        self.assertEqual(
            prediction.predicted_winner,
            self.player_a.name,
        )

        self.assertGreater(
            prediction.player_a_probability,
            50.0,
        )

        self.assertGreater(
            prediction.player_a_probability,
            prediction.player_b_probability,
        )

        contributions = {
            contribution.feature_name:
            contribution
            for contribution
            in prediction.contributions
        }

        # These are active v3.3 performance-derived features.
        self.assertGreater(
            contributions[
                "scoring_power"
            ].weighted_score,
            0.0,
        )

        self.assertGreater(
            contributions[
                "finishing_strength"
            ].weighted_score,
            0.0,
        )

        self.assertGreater(
            contributions[
                "maximums_strength"
            ].weighted_score,
            0.0,
        )

        self.assertGreater(
            contributions[
                "recent_win_rate"
            ].weighted_score,
            0.0,
        )

        # v3.3 deliberately disables these features.
        self.assertEqual(
            contributions[
                "overall_strength"
            ].weighted_score,
            0.0,
        )

        self.assertEqual(
            contributions[
                "recent_form"
            ].weighted_score,
            0.0,
        )


if __name__ == "__main__":
    unittest.main()


class CurrentMatchEnrichmentV33BeforeAfterTests(
    unittest.TestCase
):
    def setUp(self):
        self.db = create_test_session()

        self.player_a = Player(
            name="Before After A",
            elo=1500.0,
            average=90.0,
            checkout=35.0,
        )
        self.player_b = Player(
            name="Before After B",
            elo=1500.0,
            average=90.0,
            checkout=35.0,
        )

        self.db.add_all(
            [
                self.player_a,
                self.player_b,
            ]
        )
        self.db.flush()

        self.opponent_a = Player(
            name="Before After Opponent A",
            elo=1500.0,
        )
        self.opponent_b = Player(
            name="Before After Opponent B",
            elo=1500.0,
        )

        self.db.add_all(
            [
                self.opponent_a,
                self.opponent_b,
            ]
        )
        self.db.flush()

        self._seed_balanced_history()

        self.db.commit()

        self.builder = (
            AdvancedPredictionInputBuilder()
        )
        self.engine = (
            TransparentPredictionEngineV33()
        )

    def tearDown(self):
        self.db.close()

    def _add_performance(
        self,
        *,
        player,
        opponent,
        match_date,
        won,
        legs_won,
        legs_lost,
        average,
        scores_140,
        scores_180,
        checkout_attempts,
        checkouts_completed,
        highest_checkout,
        suffix,
    ):
        match = Match(
            date=match_date,
            player_a=player.name,
            player_b=opponent.name,
            winner=(
                player.name
                if won
                else opponent.name
            ),
            score=(
                f"{legs_won}-{legs_lost}"
            ),
            status="completed",
        )

        self.db.add(match)
        self.db.flush()

        checkout_percentage = (
            checkouts_completed
            / checkout_attempts
            * 100.0
            if checkout_attempts
            else None
        )

        self.db.add(
            PlayerMatchPerformance(
                match_id=match.id,
                player_id=player.id,
                opponent_id=opponent.id,
                competition_code="MODUS",
                player_external_id=(
                    f"modus-player-{player.id}"
                ),
                won_match=won,
                legs_won=legs_won,
                legs_lost=legs_lost,
                three_dart_average=average,
                scores_100_plus=8,
                scores_140_plus=scores_140,
                scores_180=scores_180,
                checkout_attempts=checkout_attempts,
                checkouts_completed=checkouts_completed,
                checkout_percentage=checkout_percentage,
                highest_checkout=highest_checkout,
                source_provider="modus-official",
                source_external_id=(
                    f"modus:statistics:{suffix}"
                ),
                source_confidence="verified",
            )
        )

    def _seed_balanced_history(self):
        start = date(2026, 7, 1)

        for index in range(5):
            match_date = (
                start
                + timedelta(
                    days=index
                )
            )

            self._add_performance(
                player=self.player_a,
                opponent=self.opponent_a,
                match_date=match_date,
                won=(index % 2 == 0),
                legs_won=(
                    4 if index % 2 == 0 else 2
                ),
                legs_lost=(
                    2 if index % 2 == 0 else 4
                ),
                average=90.0,
                scores_140=4,
                scores_180=1,
                checkout_attempts=8,
                checkouts_completed=3,
                highest_checkout=90,
                suffix=f"a-base-{index}",
            )

            self._add_performance(
                player=self.player_b,
                opponent=self.opponent_b,
                match_date=match_date,
                won=(index % 2 == 0),
                legs_won=(
                    4 if index % 2 == 0 else 2
                ),
                legs_lost=(
                    2 if index % 2 == 0 else 4
                ),
                average=90.0,
                scores_140=4,
                scores_180=1,
                checkout_attempts=8,
                checkouts_completed=3,
                highest_checkout=90,
                suffix=f"b-base-{index}",
            )

    def _predict(self):
        snapshot = self.builder.build(
            self.db,
            player_a=self.player_a,
            player_b=self.player_b,
            match_id=999002,
            competition_code="MODUS",
        )

        return self.engine.predict(
            snapshot
        )

    def test_new_enriched_match_moves_v33_probability(self):
        before = self._predict()

        self.assertAlmostEqual(
            before.player_a_probability,
            50.0,
            delta=0.5,
        )

        self._add_performance(
            player=self.player_a,
            opponent=self.opponent_a,
            match_date=date(2026, 8, 9),
            won=True,
            legs_won=4,
            legs_lost=0,
            average=105.0,
            scores_140=9,
            scores_180=4,
            checkout_attempts=6,
            checkouts_completed=4,
            highest_checkout=140,
            suffix="a-enriched",
        )

        self.db.commit()

        after = self._predict()

        self.assertGreater(
            after.player_a_probability,
            before.player_a_probability,
        )

        self.assertGreater(
            after.player_a_probability,
            50.0,
        )

        self.assertEqual(
            after.predicted_winner,
            self.player_a.name,
        )


if __name__ == "__main__":
    unittest.main()
