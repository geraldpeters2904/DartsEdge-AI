from __future__ import annotations

import unittest

from dataclasses import dataclass

from app.services.modus_sequence_reconciliation_service import (
    resolve_unique_modus_sequence,
)


@dataclass(frozen=True)
class StaleFixture:
    fixture_id: int
    player_a: str
    player_b: str


@dataclass(frozen=True)
class CompletedCard:
    match_id: int
    match_number: int | None
    player_a_name: str
    player_b_name: str


class ModusSequenceReconciliationTests(unittest.TestCase):

    def test_unique_sequence_resolves_repeated_pair_safely(self):
        stale = (
            StaleFixture(100, "Alpha", "Bravo"),
            StaleFixture(101, "Charlie", "Delta"),
            StaleFixture(102, "Alpha", "Bravo"),
        )
        completed = (
            CompletedCard(2001, 1, "Bravo", "Alpha"),
            CompletedCard(2002, 2, "Delta", "Charlie"),
            CompletedCard(2003, 3, "Alpha", "Bravo"),
        )

        result = resolve_unique_modus_sequence(
            stale,
            completed,
        )

        self.assertEqual(
            result,
            (
                (100, 2001),
                (101, 2002),
                (102, 2003),
            ),
        )

    def test_one_extra_provisional_fixture_can_be_skipped(self):
        stale = (
            StaleFixture(100, "Alpha", "Bravo"),
            StaleFixture(101, "Ghost", "Player"),
            StaleFixture(102, "Charlie", "Delta"),
            StaleFixture(103, "Echo", "Foxtrot"),
        )
        completed = (
            CompletedCard(2001, 1, "Alpha", "Bravo"),
            CompletedCard(2002, 2, "Charlie", "Delta"),
            CompletedCard(2003, 3, "Echo", "Foxtrot"),
        )

        result = resolve_unique_modus_sequence(
            stale,
            completed,
        )

        self.assertEqual(
            result,
            (
                (100, 2001),
                (102, 2002),
                (103, 2003),
            ),
        )

    def test_ambiguous_alignment_returns_no_mapping(self):
        stale = (
            StaleFixture(100, "Alpha", "Bravo"),
            StaleFixture(101, "Alpha", "Bravo"),
            StaleFixture(102, "Charlie", "Delta"),
        )
        completed = (
            CompletedCard(2001, 1, "Alpha", "Bravo"),
            CompletedCard(2002, 2, "Charlie", "Delta"),
        )

        result = resolve_unique_modus_sequence(
            stale,
            completed,
        )

        self.assertEqual(result, ())

    def test_completed_cards_use_match_number_order(self):
        stale = (
            StaleFixture(100, "Alpha", "Bravo"),
            StaleFixture(101, "Charlie", "Delta"),
            StaleFixture(102, "Echo", "Foxtrot"),
        )
        completed = (
            CompletedCard(3003, 3, "Echo", "Foxtrot"),
            CompletedCard(3001, 1, "Alpha", "Bravo"),
            CompletedCard(3002, 2, "Charlie", "Delta"),
        )

        result = resolve_unique_modus_sequence(
            stale,
            completed,
        )

        self.assertEqual(
            result,
            (
                (100, 3001),
                (101, 3002),
                (102, 3003),
            ),
        )


if __name__ == "__main__":
    unittest.main()
