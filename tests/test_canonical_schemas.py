import unittest
from datetime import datetime

from pydantic import ValidationError

from app.schemas.canonical import (
    CanonicalFixture,
    CanonicalMatchResult,
    CanonicalOddsSnapshot,
    CanonicalPlayerMatchStatistics,
    CompetitionCode,
    SourceReference,
)


class CanonicalSchemaTests(unittest.TestCase):
    def setUp(self):
        self.source = SourceReference(
            provider="test-provider",
            external_id="source-1",
            retrieved_at=datetime(2026, 7, 27, 8, 0),
            competition_code=CompetitionCode.MODUS,
        )

    def test_fixture_accepts_valid_modus_record(self):
        fixture = CanonicalFixture(
            external_id="match-100",
            competition_code="MODUS",
            competition_name="MODUS Super Series",
            scheduled_at=datetime(2026, 7, 27, 10, 0),
            player_a_external_id="player-a",
            player_a_name="Player A",
            player_b_external_id="player-b",
            player_b_name="Player B",
            throwing_first_player_external_id="player-a",
            source=self.source,
        )

        self.assertEqual(fixture.competition_code, CompetitionCode.MODUS)

    def test_fixture_rejects_same_player(self):
        with self.assertRaises(ValidationError):
            CanonicalFixture(
                external_id="match-101",
                competition_code="MODUS",
                competition_name="MODUS Super Series",
                scheduled_at=datetime(2026, 7, 27, 10, 0),
                player_a_external_id="same-player",
                player_a_name="Same Player",
                player_b_external_id="same-player",
                player_b_name="Same Player",
                source=self.source,
            )

    def test_result_rejects_winner_inconsistent_with_score(self):
        with self.assertRaises(ValidationError):
            CanonicalMatchResult(
                match_external_id="match-100",
                player_a_external_id="player-a",
                player_b_external_id="player-b",
                winner_external_id="player-b",
                player_a_legs=4,
                player_b_legs=2,
                source=self.source,
            )

    def test_statistics_preserve_missing_values(self):
        stats = CanonicalPlayerMatchStatistics(
            match_external_id="match-100",
            player_external_id="player-a",
            scores_180=None,
            source=self.source,
        )

        self.assertIsNone(stats.scores_180)
        self.assertIsNone(stats.checkout_percentage)

    def test_statistics_preserve_explicit_zero(self):
        stats = CanonicalPlayerMatchStatistics(
            match_external_id="match-100",
            player_external_id="player-a",
            scores_180=0,
            highest_checkout=0,
            source=self.source,
        )

        self.assertEqual(stats.scores_180, 0)
        self.assertEqual(stats.highest_checkout, 0)

    def test_statistics_reject_invalid_checkout_percentage(self):
        with self.assertRaises(ValidationError):
            CanonicalPlayerMatchStatistics(
                match_external_id="match-100",
                player_external_id="player-a",
                checkout_percentage=101,
                source=self.source,
            )

    def test_statistics_reject_completed_checkouts_above_attempts(self):
        with self.assertRaises(ValidationError):
            CanonicalPlayerMatchStatistics(
                match_external_id="match-100",
                player_external_id="player-a",
                checkout_attempts=4,
                checkouts_completed=5,
                source=self.source,
            )

    def test_first_180_player_must_be_match_participant(self):
        with self.assertRaises(ValidationError):
            CanonicalMatchResult(
                match_external_id="match-100",
                player_a_external_id="player-a",
                player_b_external_id="player-b",
                winner_external_id="player-a",
                player_a_legs=4,
                player_b_legs=2,
                first_180_player_external_id="player-c",
                source=self.source,
            )

    def test_odds_require_decimal_price_above_one(self):
        with self.assertRaises(ValidationError):
            CanonicalOddsSnapshot(
                match_external_id="match-100",
                market="match_winner",
                selection_external_id="player-a",
                selection_name="Player A",
                bookmaker="Test Bookmaker",
                decimal_odds=1.0,
                captured_at=datetime(2026, 7, 27, 9, 0),
                source=self.source,
            )

    def test_unknown_fields_are_rejected(self):
        with self.assertRaises(ValidationError):
            CanonicalPlayerMatchStatistics(
                match_external_id="match-100",
                player_external_id="player-a",
                invented_statistic=99,
                source=self.source,
            )


if __name__ == "__main__":
    unittest.main()
