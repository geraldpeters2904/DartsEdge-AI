import os
import tempfile
import unittest
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.match import Match
from app.models.player import Player
from app.models.player_match_performance import PlayerMatchPerformance
from app.models.odds_snapshot import OddsSnapshot
from app.services.bookmaker_capture_types import CapturedBookmakerPrice
from app.services.bookmaker_capture_service import store_price_changes
from app.services.daily_briefing_service import _value_opportunities
from app.services.prediction_centre_service import build_prediction_centre
from app.prediction_config import ACTIVE_PREDICTION_MODEL_NAME
from app.services.prediction_context_service import build_prediction_context


class V35LivePipelineIntegrationTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            suffix=".db",
            delete=False,
        )
        self.tmp.close()

        self.engine = create_engine(
            f"sqlite:///{self.tmp.name}"
        )
        Base.metadata.create_all(
            bind=self.engine
        )

        Session = sessionmaker(
            bind=self.engine
        )
        self.db = Session()

        self.player_a = Player(
            name="Integration Alpha",
            elo=1500.0,
            average=92.0,
            checkout=40.0,
            one80_rate=0.30,
        )
        self.player_b = Player(
            name="Integration Bravo",
            elo=1500.0,
            average=86.0,
            checkout=32.0,
            one80_rate=0.15,
        )

        self.db.add_all([
            self.player_a,
            self.player_b,
        ])
        self.db.commit()

        base_date = date.today() - timedelta(days=10)

        for index in range(6):
            match_date = (
                base_date
                + timedelta(days=index)
            )

            historical_match = Match(
                date=match_date,
                tournament="MODUS",
                stage="Group",
                match_format="Best of 7",
                status="completed",
                player_a=self.player_a.name,
                player_b=self.player_b.name,
                winner=(
                    self.player_a.name
                    if index < 4
                    else self.player_b.name
                ),
                score=(
                    "4-2"
                    if index < 4
                    else "2-4"
                ),
            )

            self.db.add(
                historical_match
            )
            self.db.flush()

            observed_at = datetime.combine(
                match_date,
                datetime.min.time(),
            )

            self.db.add_all([
                PlayerMatchPerformance(
                    match_id=historical_match.id,
                    player_id=self.player_a.id,
                    opponent_id=self.player_b.id,
                    competition_code="MODUS",
                    won_match=(index < 4),
                    legs_won=(
                        4 if index < 4 else 2
                    ),
                    legs_lost=(
                        2 if index < 4 else 4
                    ),
                    three_dart_average=(
                        94.0 + index
                    ),
                    first_nine_average=(
                        100.0 + index
                    ),
                    scores_100_plus=15 + index,
                    scores_140_plus=7 + index,
                    scores_180=2 + (index % 2),
                    checkout_attempts=10,
                    checkouts_completed=4,
                    checkout_percentage=40.0,
                    highest_checkout=120,
                    source_provider="integration-test",
                    source_external_id=(
                        f"a-{index}"
                    ),
                    observed_at=observed_at,
                ),
                PlayerMatchPerformance(
                    match_id=historical_match.id,
                    player_id=self.player_b.id,
                    opponent_id=self.player_a.id,
                    competition_code="MODUS",
                    won_match=(index >= 4),
                    legs_won=(
                        2 if index < 4 else 4
                    ),
                    legs_lost=(
                        4 if index < 4 else 2
                    ),
                    three_dart_average=(
                        84.0 + index
                    ),
                    first_nine_average=(
                        90.0 + index
                    ),
                    scores_100_plus=10 + index,
                    scores_140_plus=4 + index,
                    scores_180=index % 2,
                    checkout_attempts=10,
                    checkouts_completed=3,
                    checkout_percentage=30.0,
                    highest_checkout=96,
                    source_provider="integration-test",
                    source_external_id=(
                        f"b-{index}"
                    ),
                    observed_at=observed_at,
                ),
            ])

        self.fixture = Match(
            date=date.today(),
            tournament="MODUS",
            stage="Group",
            match_format="Best of 7",
            status="scheduled",
            player_a=self.player_a.name,
            player_b=self.player_b.name,
        )

        self.db.add(
            self.fixture
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        os.unlink(
            self.tmp.name
        )

    def test_real_history_reaches_active_v35_model(self):
        context = build_prediction_context(
            self.db,
            self.fixture.id,
        )

        self.assertEqual(
            ACTIVE_PREDICTION_MODEL_NAME,
            "transparent-v3.5",
        )
        self.assertEqual(
            context.model_name,
            ACTIVE_PREDICTION_MODEL_NAME,
        )
        self.assertEqual(
            context.model_version,
            "transparent-v3.5",
        )

        self.assertEqual(
            context.player_a_history_matches,
            6,
        )
        self.assertEqual(
            context.player_b_history_matches,
            6,
        )

        self.assertGreater(
            context.player_a_probability,
            0.0,
        )
        self.assertLess(
            context.player_a_probability,
            100.0,
        )
        self.assertGreater(
            context.player_b_probability,
            0.0,
        )
        self.assertLess(
            context.player_b_probability,
            100.0,
        )

        self.assertAlmostEqual(
            (
                context.player_a_probability
                + context.player_b_probability
            ),
            100.0,
            places=3,
        )

        self.assertIn(
            context.predicted_winner,
            (
                self.player_a.name,
                self.player_b.name,
            ),
        )


    def test_real_bookmaker_price_persists_against_fixture(self):
        captured_at = datetime.utcnow()

        price = CapturedBookmakerPrice(
            fixture_date=self.fixture.date,
            tournament=self.fixture.tournament,
            player_a=self.fixture.player_a,
            player_b=self.fixture.player_b,
            market="match_winner",
            selection=self.fixture.player_a,
            bookmaker="Paddy Power",
            decimal_odds=2.50,
            captured_at=captured_at,
            provider_id="integration-price-1",
        )

        result = store_price_changes(
            self.db,
            [price],
        )

        self.assertEqual(
            result["stored"],
            1,
        )
        self.assertEqual(
            result["unchanged"],
            0,
        )
        self.assertEqual(
            result["skipped"],
            0,
        )

        snapshots = (
            self.db.query(OddsSnapshot)
            .all()
        )

        self.assertEqual(
            len(snapshots),
            1,
        )

        snapshot = snapshots[0]

        self.assertEqual(
            snapshot.fixture_id,
            self.fixture.id,
        )
        self.assertEqual(
            snapshot.bookmaker_code,
            "paddypower",
        )
        self.assertEqual(
            snapshot.market,
            "match_winner",
        )
        self.assertEqual(
            snapshot.selection,
            self.fixture.player_a,
        )
        self.assertAlmostEqual(
            snapshot.decimal_odds,
            2.50,
        )
        self.assertAlmostEqual(
            snapshot.implied_probability,
            40.0,
        )
        self.assertEqual(
            snapshot.provider_id,
            "integration-price-1",
        )


    def test_real_prediction_odds_value_and_prediction_centre_join(self):
        captured_at = datetime.utcnow()

        prices = [
            CapturedBookmakerPrice(
                fixture_date=self.fixture.date,
                tournament=self.fixture.tournament,
                player_a=self.fixture.player_a,
                player_b=self.fixture.player_b,
                market="match_winner",
                selection=self.fixture.player_a,
                bookmaker="Paddy Power",
                decimal_odds=3.00,
                captured_at=captured_at,
                provider_id="integration-alpha",
            ),
            CapturedBookmakerPrice(
                fixture_date=self.fixture.date,
                tournament=self.fixture.tournament,
                player_a=self.fixture.player_a,
                player_b=self.fixture.player_b,
                market="match_winner",
                selection=self.fixture.player_b,
                bookmaker="Paddy Power",
                decimal_odds=3.00,
                captured_at=captured_at,
                provider_id="integration-bravo",
            ),
        ]

        persistence = store_price_changes(
            self.db,
            prices,
        )

        self.assertEqual(
            persistence["stored"],
            2,
        )
        self.assertEqual(
            persistence["skipped"],
            0,
        )

        values = _value_opportunities(
            self.db,
            limit=10,
        )

        matching_values = [
            row
            for row in values
            if row.get("match_id") == self.fixture.id
        ]

        self.assertEqual(
            len(matching_values),
            1,
        )

        value = matching_values[0]

        self.assertEqual(
            value["model_name"],
            ACTIVE_PREDICTION_MODEL_NAME,
        )
        self.assertIsNotNone(
            value["price"],
        )
        self.assertIsNotNone(
            value["assessment"],
        )
        self.assertAlmostEqual(
            value["price"].decimal_odds,
            3.00,
        )
        self.assertEqual(
            value["price"].fixture_id,
            self.fixture.id,
        )

        centre = build_prediction_centre(
            self.db,
            limit=10,
        )

        cards = centre.get(
            "cards",
            centre
            if isinstance(centre, list)
            else [],
        )

        matching_cards = [
            card
            for card in cards
            if (
                (
                    card.get("fixture").id
                    if card.get("fixture") is not None
                    else None
                )
                == self.fixture.id
            )
        ]

        self.assertEqual(
            len(matching_cards),
            1,
        )

        card = matching_cards[0]

        self.assertIsNotNone(
            card.get("opportunity"),
        )
        self.assertIsNotNone(
            card.get("price"),
        )
        self.assertIsNotNone(
            card.get("assessment"),
        )

        self.assertEqual(
            card["opportunity"]["model_name"],
            ACTIVE_PREDICTION_MODEL_NAME,
        )
        self.assertEqual(
            card["price"].fixture_id,
            self.fixture.id,
        )
        self.assertNotEqual(
            card.get("status"),
            "Odds required",
        )


if __name__ == "__main__":
    unittest.main()
