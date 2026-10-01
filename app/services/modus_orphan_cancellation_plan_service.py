from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import Sequence, Tuple

from app.services.modus_stale_scope_grouping_service import (
    StaleFixtureScopeGroup,
)


@dataclass(frozen=True)
class OrphanCancellationPlan:
    resolved: bool
    fixture_ids: Tuple[int, ...]
    reason: str


def _normalise_name(value: object) -> str:
    return " ".join(
        str(value or "").strip().casefold().split()
    )


def _pair_key(
    player_a: object,
    player_b: object,
) -> Tuple[str, str]:
    return tuple(
        sorted(
            (
                _normalise_name(player_a),
                _normalise_name(player_b),
            )
        )
    )


def _completed_pair_counts(
    completed_cards: Sequence[object],
) -> Counter:
    return Counter(
        _pair_key(
            getattr(card, "player_a_name", ""),
            getattr(card, "player_b_name", ""),
        )
        for card in completed_cards
    )


def _balanced_round_robin_repetitions(
    completed_cards: Sequence[object],
) -> int:
    cards = tuple(completed_cards)

    if not cards:
        return 0

    players = {
        _normalise_name(name)
        for card in cards
        for name in (
            getattr(card, "player_a_name", ""),
            getattr(card, "player_b_name", ""),
        )
        if _normalise_name(name)
    }

    if len(players) < 2:
        return 0

    expected_pairs = {
        tuple(sorted(pair))
        for pair in combinations(
            sorted(players),
            2,
        )
    }

    pair_counts = _completed_pair_counts(cards)

    if set(pair_counts) != expected_pairs:
        return 0

    counts = set(pair_counts.values())

    if len(counts) != 1:
        return 0

    repetitions = next(iter(counts))

    if repetitions < 1:
        return 0

    expected_match_count = (
        len(expected_pairs) * repetitions
    )

    if len(cards) != expected_match_count:
        return 0

    return int(repetitions)


def build_orphan_cancellation_plan(
    group: StaleFixtureScopeGroup,
    completed_cards: Sequence[object],
) -> OrphanCancellationPlan:
    fixtures = tuple(group.fixtures)

    if not fixtures:
        return OrphanCancellationPlan(
            resolved=False,
            fixture_ids=(),
            reason="No stale fixtures were supplied.",
        )

    repetitions = _balanced_round_robin_repetitions(
        completed_cards
    )

    if repetitions == 0:
        return OrphanCancellationPlan(
            resolved=False,
            fixture_ids=(),
            reason=(
                "Official completed cards do not prove a complete "
                "balanced round-robin structure."
            ),
        )

    pair_counts = _completed_pair_counts(
        completed_cards
    )

    candidates = []

    for fixture in fixtures:
        pair = _pair_key(
            fixture.player_a,
            fixture.player_b,
        )

        if (
            pair[0]
            and pair[1]
            and pair_counts.get(pair, 0) == repetitions
        ):
            candidates.append(
                int(fixture.fixture_id)
            )

    if not candidates:
        return OrphanCancellationPlan(
            resolved=False,
            fixture_ids=(),
            reason=(
                "No stale fixture pairing is already fully accounted "
                "for by the completed round robin."
            ),
        )

    return OrphanCancellationPlan(
        resolved=True,
        fixture_ids=tuple(candidates),
        reason=(
            "Official completed cards form a complete balanced "
            f"{repetitions}-round-robin and the stale fixture "
            "pairing is already fully represented."
        ),
    )
