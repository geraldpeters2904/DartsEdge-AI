import unittest
from types import SimpleNamespace
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from app.models.match import Match
from app.models.player import Player
from app.models.player_match_performance import PlayerMatchPerformance
from app.models.odds_snapshot import OddsSnapshot
from app.services.value_board_service import (
    _current_player_total_180_line,
    _current_total_180_line,
    _current_most_180_market,
    _most_180_rows,
    _player_180_expectation,
    _player_total_180_rows,
    _total_180_rows,
    build_value_board,
)
from tests.helpers.database import create_test_session


class Player180ExpectationTests(unittest.TestCase):

    def setUp(self):
        self.db = create_test_session()

    def tearDown(self):
        self.db.close()

    def test_uses_only_matches_with_reported_180_data(self):
        player = Player(name="Justin Smith")
        opponent = Player(name="Opponent")
        self.db.add_all([player, opponent])
        self.db.flush()

        matches = []
        for index in range(3):
            match = Match(
                date=date(2026, 9, index + 1),
                tournament="MODUS Super Series",
                player_a="Justin Smith",
                player_b="Opponent",
                status="completed",
            )
            self.db.add(match)
            self.db.flush()
            matches.append(match)

        self.db.add_all(
            [
                PlayerMatchPerformance(
                    match_id=matches[0].id,
                    player_id=player.id,
                    opponent_id=opponent.id,
                    scores_180=0,
                    source_provider="test",
                ),
                PlayerMatchPerformance(
                    match_id=matches[1].id,
                    player_id=player.id,
                    opponent_id=opponent.id,
                    scores_180=2,
                    source_provider="test",
                ),
                PlayerMatchPerformance(
                    match_id=matches[2].id,
                    player_id=player.id,
                    opponent_id=opponent.id,
                    scores_180=None,
                    source_provider="test",
                ),
            ]
        )
        self.db.commit()

        result = _player_180_expectation(
            self.db,
            "Justin Smith",
        )

        self.assertEqual(result["matches"], 2)
        self.assertEqual(result["total_180s"], 2)
        self.assertEqual(result["expected"], 1.0)

    def test_returns_none_when_player_has_no_reported_180_data(self):
        player = Player(name="Danny Goddard")
        opponent = Player(name="Opponent")
        self.db.add_all([player, opponent])
        self.db.flush()

        match = Match(
            date=date(2026, 9, 1),
            tournament="MODUS Super Series",
            player_a="Danny Goddard",
            player_b="Opponent",
            status="completed",
        )
        self.db.add(match)
        self.db.flush()

        self.db.add(
            PlayerMatchPerformance(
                match_id=match.id,
                player_id=player.id,
                opponent_id=opponent.id,
                scores_180=None,
                source_provider="test",
            )
        )
        self.db.commit()

        self.assertIsNone(
            _player_180_expectation(
                self.db,
                "Danny Goddard",
            )
        )


class PlayerTotal180LineTests(unittest.TestCase):

    def test_uses_most_recent_line_and_ignores_stale_line(self):
        from datetime import datetime

        rows = [
            SimpleNamespace(
                id=144,
                captured_at=datetime(2026, 9, 4, 14, 25, 48),
                selection="Justin Smith | Over (+0.5)",
                decimal_odds=1.363636,
            ),
            SimpleNamespace(
                id=145,
                captured_at=datetime(2026, 9, 4, 14, 25, 48),
                selection="Justin Smith | Under (+0.5)",
                decimal_odds=2.875,
            ),
            SimpleNamespace(
                id=230,
                captured_at=datetime(2026, 9, 4, 16, 17, 40),
                selection="Justin Smith | Over (+1.5)",
                decimal_odds=2.75,
            ),
            SimpleNamespace(
                id=231,
                captured_at=datetime(2026, 9, 4, 16, 17, 40),
                selection="Justin Smith | Under (+1.5)",
                decimal_odds=1.4,
            ),
        ]

        current = _current_player_total_180_line(
            rows,
            "Justin Smith",
        )

        self.assertEqual(current["line"], 1.5)
        self.assertEqual(current["over_odds"], 2.75)
        self.assertEqual(current["under_odds"], 1.4)


class Total180LineTests(unittest.TestCase):

    def test_uses_newest_complete_total_180_line(self):
        rows = [
            SimpleNamespace(
                id=1,
                selection="Over (+2.5)",
                decimal_odds=2.25,
                captured_at=datetime(2026, 9, 4, 12, 0, 0),
            ),
            SimpleNamespace(
                id=2,
                selection="Under (+2.5)",
                decimal_odds=1.57,
                captured_at=datetime(2026, 9, 4, 12, 0, 0),
            ),
            SimpleNamespace(
                id=3,
                selection="Over (+3.5)",
                decimal_odds=2.50,
                captured_at=datetime(2026, 9, 5, 12, 0, 0),
            ),
            SimpleNamespace(
                id=4,
                selection="Under (+3.5)",
                decimal_odds=1.50,
                captured_at=datetime(2026, 9, 5, 12, 0, 0),
            ),
        ]

        current = _current_total_180_line(rows)

        self.assertEqual(current["line"], 3.5)
        self.assertEqual(current["over_odds"], 2.50)
        self.assertEqual(current["under_odds"], 1.50)


class Most180MarketTests(unittest.TestCase):
    def test_uses_earliest_complete_three_way_market(self):
        rows = [
            SimpleNamespace(
                id=1,
                selection="Player A",
                decimal_odds=2.80,
                captured_at=datetime(2026, 9, 4, 12, 0, 0),
            ),
            SimpleNamespace(
                id=2,
                selection="Draw",
                decimal_odds=3.10,
                captured_at=datetime(2026, 9, 4, 12, 0, 0),
            ),
            SimpleNamespace(
                id=3,
                selection="Player B",
                decimal_odds=2.37,
                captured_at=datetime(2026, 9, 4, 12, 0, 0),
            ),
            SimpleNamespace(
                id=4,
                selection="Player A",
                decimal_odds=2.50,
                captured_at=datetime(2026, 9, 5, 12, 0, 0),
            ),
            SimpleNamespace(
                id=5,
                selection="Draw",
                decimal_odds=3.25,
                captured_at=datetime(2026, 9, 5, 12, 0, 0),
            ),
            SimpleNamespace(
                id=6,
                selection="Player B",
                decimal_odds=2.75,
                captured_at=datetime(2026, 9, 5, 12, 0, 0),
            ),
        ]

        current = _current_most_180_market(
            rows,
            "Player A",
            "Player B",
        )

        self.assertEqual(current["player_a_odds"], 2.80)
        self.assertEqual(current["draw_odds"], 3.10)
        self.assertEqual(current["player_b_odds"], 2.37)


class Most180ValueRowsTests(unittest.TestCase):
    def setUp(self):
        self.db = create_test_session()

    def tearDown(self):
        self.db.close()

    def test_builds_three_way_rows_when_both_players_have_history(self):
        player_a = Player(name="Player A")
        player_b = Player(name="Player B")
        self.db.add_all([player_a, player_b])
        self.db.flush()

        samples = [
            (player_a, player_b, 2),
            (player_a, player_b, 1),
            (player_b, player_a, 0),
            (player_b, player_a, 1),
        ]

        for index, (player, opponent, scores_180) in enumerate(
            samples,
            start=1,
        ):
            match = Match(
                date=date(2026, 8, index),
                tournament="MODUS Super Series",
                player_a=player.name,
                player_b=opponent.name,
                status="completed",
            )
            self.db.add(match)
            self.db.flush()

            self.db.add(
                PlayerMatchPerformance(
                    match_id=match.id,
                    player_id=player.id,
                    opponent_id=opponent.id,
                    scores_180=scores_180,
                    source_provider="test",
                )
            )

        fixture = Match(
            date=date(2026, 9, 6),
            tournament="MODUS Super Series",
            player_a="Player A",
            player_b="Player B",
            status="scheduled",
        )
        self.db.add(fixture)
        self.db.flush()

        captured_at = datetime(2026, 9, 6, 12, 0, 0)

        self.db.add_all(
            [
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="most_180s",
                    selection="Player A",
                    decimal_odds=2.50,
                    captured_at=captured_at,
                ),
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="most_180s",
                    selection="Draw",
                    decimal_odds=3.25,
                    captured_at=captured_at,
                ),
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="most_180s",
                    selection="Player B",
                    decimal_odds=2.75,
                    captured_at=captured_at,
                ),
            ]
        )

        self.db.commit()

        rows = _most_180_rows(
            self.db,
            fixture,
        )

        self.assertEqual(len(rows), 3)

        by_selection = {
            row["selection"]: row
            for row in rows
        }

        self.assertEqual(
            set(by_selection),
            {
                "Player A Most 180s",
                "Draw Most 180s",
                "Player B Most 180s",
            },
        )

        self.assertEqual(
            by_selection["Player A Most 180s"]["market"],
            "Most 180s",
        )
        self.assertEqual(
            by_selection["Player A Most 180s"]["market_odds"],
            2.50,
        )
        self.assertEqual(
            by_selection["Draw Most 180s"]["market_odds"],
            3.25,
        )
        self.assertEqual(
            by_selection["Player B Most 180s"]["market_odds"],
            2.75,
        )

        total_probability = sum(
            row["probability"]
            for row in rows
        )
        self.assertAlmostEqual(
            total_probability,
            100.0,
            delta=0.2,
        )

    def test_skips_when_either_player_has_no_180_history(self):
        player_a = Player(name="Player A")
        player_b = Player(name="Player B")
        self.db.add_all([player_a, player_b])
        self.db.flush()

        match = Match(
            date=date(2026, 8, 1),
            tournament="MODUS Super Series",
            player_a="Player A",
            player_b="Player B",
            status="completed",
        )
        self.db.add(match)
        self.db.flush()

        self.db.add(
            PlayerMatchPerformance(
                match_id=match.id,
                player_id=player_a.id,
                opponent_id=player_b.id,
                scores_180=1,
                source_provider="test",
            )
        )

        fixture = Match(
            date=date(2026, 9, 6),
            tournament="MODUS Super Series",
            player_a="Player A",
            player_b="Player B",
            status="scheduled",
        )
        self.db.add(fixture)
        self.db.commit()

        self.assertEqual(
            _most_180_rows(
                self.db,
                fixture,
            ),
            [],
        )


class PlayerTotal180ValueRowsTests(unittest.TestCase):

    def setUp(self):
        self.db = create_test_session()

    def tearDown(self):
        self.db.close()

    def test_builds_over_and_under_rows_from_reported_history(self):
        player = Player(name="Justin Smith")
        opponent = Player(name="Opponent")
        self.db.add_all([player, opponent])
        self.db.flush()

        for index, scores_180 in enumerate((0, 2), start=1):
            match = Match(
                date=date(2026, 8, index),
                tournament="MODUS Super Series",
                player_a="Justin Smith",
                player_b="Opponent",
                status="completed",
            )
            self.db.add(match)
            self.db.flush()
            self.db.add(
                PlayerMatchPerformance(
                    match_id=match.id,
                    player_id=player.id,
                    opponent_id=opponent.id,
                    scores_180=scores_180,
                    source_provider="test",
                )
            )

        fixture = Match(
            date=date(2026, 9, 6),
            tournament="MODUS Super Series",
            player_a="Justin Smith",
            player_b="Opponent",
            status="scheduled",
        )
        self.db.add(fixture)
        self.db.flush()

        captured_at = datetime(2026, 9, 6, 12, 0, 0)
        self.db.add_all(
            [
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="player_total_180s",
                    selection="Justin Smith | Over (+1.5)",
                    decimal_odds=2.75,
                    captured_at=captured_at,
                ),
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="player_total_180s",
                    selection="Justin Smith | Under (+1.5)",
                    decimal_odds=1.40,
                    captured_at=captured_at,
                ),
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="total_180s",
                    selection="Over (+2.5)",
                    decimal_odds=2.20,
                    captured_at=captured_at,
                ),
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="total_180s",
                    selection="Under (+2.5)",
                    decimal_odds=1.62,
                    captured_at=captured_at,
                ),
            ]
        )
        self.db.commit()

        rows = _player_total_180_rows(
            self.db,
            fixture,
            "Justin Smith",
        )

        self.assertEqual(len(rows), 2)

        by_selection = {
            row["selection"]: row
            for row in rows
        }

        over = by_selection["Justin Smith Over 1.5 180s"]
        under = by_selection["Justin Smith Under 1.5 180s"]

        self.assertEqual(over["market"], "Player Total 180s")
        self.assertEqual(over["market_odds"], 2.75)
        self.assertEqual(under["market_odds"], 1.40)

        self.assertEqual(over["history_matches"], 2)
        self.assertEqual(over["expected_180s"], 1.0)

        self.assertAlmostEqual(
            over["probability"],
            26.42,
            places=2,
        )
        self.assertAlmostEqual(
            under["probability"],
            73.58,
            places=2,
        )

        self.assertAlmostEqual(
            over["fair_odds"],
            3.78,
            places=2,
        )
        self.assertAlmostEqual(
            under["fair_odds"],
            1.36,
            places=2,
        )

    def test_skips_player_without_reported_180_history(self):
        player = Player(name="Danny Goddard")
        opponent = Player(name="Opponent")
        self.db.add_all([player, opponent])
        self.db.flush()

        fixture = Match(
            date=date(2026, 9, 6),
            tournament="MODUS Super Series",
            player_a="Danny Goddard",
            player_b="Opponent",
            status="scheduled",
        )
        self.db.add(fixture)
        self.db.commit()

        self.assertEqual(
            _player_total_180_rows(
                self.db,
                fixture,
                "Danny Goddard",
            ),
            [],
        )


class Total180ValueRowsTests(unittest.TestCase):

    def setUp(self):
        self.db = create_test_session()

    def tearDown(self):
        self.db.close()

    def test_builds_total_180_rows_when_both_players_have_history(self):
        player_a = Player(name="Player A")
        player_b = Player(name="Player B")
        self.db.add_all([player_a, player_b])
        self.db.flush()

        samples = [
            (player_a, player_b, 1),
            (player_a, player_b, 2),
            (player_b, player_a, 0),
            (player_b, player_a, 1),
        ]

        for index, (player, opponent, scores_180) in enumerate(
            samples,
            start=1,
        ):
            match = Match(
                date=date(2026, 8, index),
                tournament="MODUS Super Series",
                player_a=player.name,
                player_b=opponent.name,
                status="completed",
            )
            self.db.add(match)
            self.db.flush()

            self.db.add(
                PlayerMatchPerformance(
                    match_id=match.id,
                    player_id=player.id,
                    opponent_id=opponent.id,
                    scores_180=scores_180,
                    source_provider="test",
                )
            )

        fixture = Match(
            date=date(2026, 9, 6),
            tournament="MODUS Super Series",
            player_a="Player A",
            player_b="Player B",
            status="scheduled",
        )
        self.db.add(fixture)
        self.db.flush()

        captured_at = datetime(2026, 9, 6, 12, 0, 0)

        self.db.add_all(
            [
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="total_180s",
                    selection="Over (+2.5)",
                    decimal_odds=2.20,
                    captured_at=captured_at,
                ),
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="total_180s",
                    selection="Under (+2.5)",
                    decimal_odds=1.62,
                    captured_at=captured_at,
                ),
            ]
        )
        self.db.commit()

        rows = _total_180_rows(
            self.db,
            fixture,
        )

        self.assertEqual(len(rows), 2)

        by_selection = {
            row["selection"]: row
            for row in rows
        }

        over = by_selection["Over 2.5 Total 180s"]
        under = by_selection["Under 2.5 Total 180s"]

        self.assertEqual(over["market"], "Total 180s")
        self.assertEqual(over["player_a_history_matches"], 2)
        self.assertEqual(over["player_b_history_matches"], 2)
        self.assertEqual(over["expected_180s"], 2.0)
        self.assertEqual(over["market_odds"], 2.20)
        self.assertEqual(under["market_odds"], 1.62)

    def test_skips_total_180s_when_either_player_has_no_history(self):
        player_a = Player(name="Player A")
        player_b = Player(name="Player B")
        self.db.add_all([player_a, player_b])
        self.db.flush()

        match = Match(
            date=date(2026, 8, 1),
            tournament="MODUS Super Series",
            player_a="Player A",
            player_b="Player B",
            status="completed",
        )
        self.db.add(match)
        self.db.flush()

        self.db.add(
            PlayerMatchPerformance(
                match_id=match.id,
                player_id=player_a.id,
                opponent_id=player_b.id,
                scores_180=1,
                source_provider="test",
            )
        )

        fixture = Match(
            date=date(2026, 9, 6),
            tournament="MODUS Super Series",
            player_a="Player A",
            player_b="Player B",
            status="scheduled",
        )
        self.db.add(fixture)
        self.db.commit()

        self.assertEqual(
            _total_180_rows(
                self.db,
                fixture,
            ),
            [],
        )


class ValueBoardServiceTests(unittest.TestCase):
    @patch(
        "app.services.value_board_service.context_to_opportunity"
    )
    @patch(
        "app.services.value_board_service.build_prediction_context"
    )
    @patch(
        "app.services.value_board_service.get_scheduled_fixtures"
    )
    def test_attaches_latest_paddy_power_match_odds(
        self,
        get_scheduled_fixtures,
        build_prediction_context,
        context_to_opportunity,
    ):
        fixture = SimpleNamespace(
            id=17620,
            date=None,
            tournament="MODUS Super Series",
            stage=None,
            match_format=None,
            player_a="Richard McKee",
            player_b="Martyn Turner",
        )

        get_scheduled_fixtures.return_value = [fixture]

        build_prediction_context.return_value = SimpleNamespace()

        context_to_opportunity.return_value = {
            "match_id": 17620,
            "date": None,
            "tournament": "MODUS Super Series",
            "player_a": "Richard McKee",
            "player_b": "Martyn Turner",
            "selection": "Martyn Turner",
            "probability": 50.86,
            "fair_odds": 1.97,
            "model_name": "transparent-v3.5",
            "model_version": "transparent-v3.5",
            "player_a_probability": 49.14,
            "player_b_probability": 50.86,
            "model_confidence": 70.516,
            "model_score": 53.0,
            "player_a_history_matches": 61,
            "player_b_history_matches": 164,
            "explanations": [],
            "contributions": [],
        }

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            SimpleNamespace(
                decimal_odds=2.1,
                bookmaker_code="paddypower",
            )
        )

        rows = build_value_board(db)

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["selection"],
            "Martyn Turner",
        )
        self.assertEqual(
            rows[0]["market"],
            "Match Winner",
        )
        self.assertEqual(
            rows[0]["probability"],
            50.86,
        )
        self.assertEqual(
            rows[0]["fair_odds"],
            1.97,
        )
        self.assertEqual(
            rows[0]["market_odds"],
            2.1,
        )
        self.assertEqual(
            rows[0]["bookmaker"],
            "Paddy Power",
        )
        self.assertEqual(
            rows[0]["edge"],
            3.24,
        )
        self.assertEqual(
            rows[0]["expected_value_percent"],
            6.81,
        )
        self.assertTrue(
            rows[0]["is_value_confirmed"],
        )
        self.assertEqual(
            rows[0]["status"],
            "Value confirmed",
        )
        self.assertEqual(
            rows[0]["action"],
            "Consider",
        )

    @patch(
        "app.services.value_board_service.context_to_opportunity"
    )
    @patch(
        "app.services.value_board_service.build_prediction_context"
    )
    @patch(
        "app.services.value_board_service.get_scheduled_fixtures"
    )
    def test_ranks_stronger_confirmed_value_ahead_of_win_probability(
        self,
        get_scheduled_fixtures,
        build_prediction_context,
        context_to_opportunity,
    ):
        fixtures = [
            SimpleNamespace(
                id=1,
                date=None,
                tournament="MODUS Super Series",
                stage=None,
                match_format=None,
                player_a="Player A",
                player_b="Player B",
            ),
            SimpleNamespace(
                id=2,
                date=None,
                tournament="MODUS Super Series",
                stage=None,
                match_format=None,
                player_a="Player C",
                player_b="Player D",
            ),
        ]
        get_scheduled_fixtures.return_value = fixtures
        build_prediction_context.side_effect = [
            SimpleNamespace(),
            SimpleNamespace(),
        ]
        context_to_opportunity.side_effect = [
            {
                "selection": "Player A",
                "probability": 65.0,
                "fair_odds": 1.54,
            },
            {
                "selection": "Player C",
                "probability": 55.0,
                "fair_odds": 1.82,
            },
        ]

        db = MagicMock()
        query = db.query.return_value
        filtered = query.filter.return_value
        ordered = filtered.order_by.return_value
        ordered.first.side_effect = [
            SimpleNamespace(
                decimal_odds=1.60,
                bookmaker_code="paddypower",
            ),
            SimpleNamespace(
                decimal_odds=2.20,
                bookmaker_code="paddypower",
            ),
        ]

        rows = build_value_board(db)

        self.assertEqual(
            [row["fixture_id"] for row in rows],
            [2, 1],
        )
        self.assertGreater(
            rows[0]["expected_value_percent"],
            rows[1]["expected_value_percent"],
        )



class ValueBoardPlayer180IntegrationTests(unittest.TestCase):

    def setUp(self):
        self.db = create_test_session()

    def tearDown(self):
        self.db.close()

    @patch(
        "app.services.value_board_service.context_to_opportunity"
    )
    @patch(
        "app.services.value_board_service.build_prediction_context"
    )
    def test_build_value_board_includes_player_total_180_rows(
        self,
        build_prediction_context,
        context_to_opportunity,
    ):
        justin = Player(name="Justin Smith")
        opponent = Player(name="Opponent")
        self.db.add_all([justin, opponent])
        self.db.flush()

        for index, scores_180 in enumerate((0, 2), start=1):
            match = Match(
                date=date(2026, 8, index),
                tournament="MODUS Super Series",
                player_a="Justin Smith",
                player_b="Opponent",
                status="completed",
            )
            self.db.add(match)
            self.db.flush()

            self.db.add(
                PlayerMatchPerformance(
                    match_id=match.id,
                    player_id=justin.id,
                    opponent_id=opponent.id,
                    scores_180=scores_180,
                    source_provider="test",
                )
            )

        for index, scores_180 in enumerate((1, 1), start=3):
            match = Match(
                date=date(2026, 8, index),
                tournament="MODUS Super Series",
                player_a="Opponent",
                player_b="Justin Smith",
                status="completed",
            )
            self.db.add(match)
            self.db.flush()

            self.db.add(
                PlayerMatchPerformance(
                    match_id=match.id,
                    player_id=opponent.id,
                    opponent_id=justin.id,
                    scores_180=scores_180,
                    source_provider="test",
                )
            )

        fixture = Match(
            date=date(2026, 9, 6),
            tournament="MODUS Super Series",
            stage=None,
            match_format=None,
            player_a="Justin Smith",
            player_b="Opponent",
            status="scheduled",
        )
        self.db.add(fixture)
        self.db.flush()

        captured_at = datetime(2026, 9, 6, 12, 0, 0)

        self.db.add_all(
            [
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="match_winner",
                    selection="Justin Smith",
                    decimal_odds=2.10,
                    captured_at=captured_at,
                ),
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="player_total_180s",
                    selection="Justin Smith | Over (+1.5)",
                    decimal_odds=2.75,
                    captured_at=captured_at,
                ),
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="player_total_180s",
                    selection="Justin Smith | Under (+1.5)",
                    decimal_odds=1.40,
                    captured_at=captured_at,
                ),
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="total_180s",
                    selection="Over (+2.5)",
                    decimal_odds=2.20,
                    captured_at=captured_at,
                ),
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="total_180s",
                    selection="Under (+2.5)",
                    decimal_odds=1.62,
                    captured_at=captured_at,
                ),
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="most_180s",
                    selection="Justin Smith",
                    decimal_odds=2.50,
                    captured_at=captured_at,
                ),
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="most_180s",
                    selection="Draw",
                    decimal_odds=3.25,
                    captured_at=captured_at,
                ),
                OddsSnapshot(
                    fixture_id=fixture.id,
                    bookmaker_code="paddypower",
                    market="most_180s",
                    selection="Opponent",
                    decimal_odds=2.75,
                    captured_at=captured_at,
                ),
            ]
        )
        self.db.commit()

        build_prediction_context.return_value = SimpleNamespace()
        context_to_opportunity.return_value = {
            "selection": "Justin Smith",
            "probability": 55.0,
            "fair_odds": 1.82,
        }

        rows = build_value_board(self.db)

        self.assertEqual(len(rows), 8)

        markets = [row["market"] for row in rows]
        self.assertEqual(markets.count("Total 180s"), 2)
        self.assertEqual(markets.count("Most 180s"), 3)


        self.assertEqual(
            markets.count("Match Winner"),
            1,
        )
        self.assertEqual(
            markets.count("Player Total 180s"),
            2,
        )

        player_180_selections = {
            row["selection"]
            for row in rows
            if row["market"] == "Player Total 180s"
        }

        self.assertEqual(
            player_180_selections,
            {
                "Justin Smith Over 1.5 180s",
                "Justin Smith Under 1.5 180s",
            },
        )


if __name__ == "__main__":
    unittest.main()
