from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from app.services.modus_sequence_reconciliation_service import (
    resolve_unique_modus_sequence,
)
from app.services.modus_stale_scope_grouping_service import (
    StaleFixtureScopeGroup,
)


@dataclass(frozen=True)
class StaleReconciliationPlan:
    resolved: bool
    mappings: Tuple[Tuple[int, int], ...]
    unmatched_fixture_ids: Tuple[int, ...]


def _completed_cards_in_order(
    completed_cards: Sequence[object],
) -> Tuple[object, ...]:
    cards = tuple(completed_cards)

    if not cards:
        return ()

    match_numbers = [
        getattr(card, "match_number", None)
        for card in cards
    ]

    if (
        all(number is not None for number in match_numbers)
        and len(set(match_numbers)) == len(match_numbers)
    ):
        return tuple(
            sorted(
                cards,
                key=lambda card: int(card.match_number),
            )
        )

    return tuple(
        sorted(
            cards,
            key=lambda card: int(card.match_id),
        )
    )


def _build_plan_from_mappings(
    group: StaleFixtureScopeGroup,
    mappings,
) -> StaleReconciliationPlan:
    mapped_fixture_ids = {
        int(fixture_id)
        for fixture_id, _ in mappings
    }

    unmatched = tuple(
        int(item.fixture_id)
        for item in group.fixtures
        if int(item.fixture_id) not in mapped_fixture_ids
    )

    return StaleReconciliationPlan(
        resolved=True,
        mappings=tuple(mappings),
        unmatched_fixture_ids=unmatched,
    )


def build_stale_reconciliation_plan(
    group: StaleFixtureScopeGroup,
    completed_cards: Sequence[object],
) -> StaleReconciliationPlan:
    ordered_cards = _completed_cards_in_order(
        completed_cards
    )

    mappings = resolve_unique_modus_sequence(
        group.fixtures,
        ordered_cards,
    )

    if mappings:
        return _build_plan_from_mappings(
            group,
            mappings,
        )

    stale_count = len(group.fixtures)

    if (
        stale_count == 0
        or len(ordered_cards) <= stale_count
    ):
        return StaleReconciliationPlan(
            resolved=False,
            mappings=(),
            unmatched_fixture_ids=(),
        )

    resolved_windows = []

    for start in range(
        0,
        len(ordered_cards) - stale_count + 1,
    ):
        window = ordered_cards[
            start:start + stale_count
        ]

        window_mappings = resolve_unique_modus_sequence(
            group.fixtures,
            window,
        )

        if window_mappings:
            resolved_windows.append(
                window_mappings
            )

            if len(resolved_windows) > 1:
                return StaleReconciliationPlan(
                    resolved=False,
                    mappings=(),
                    unmatched_fixture_ids=(),
                )

    if len(resolved_windows) != 1:
        return StaleReconciliationPlan(
            resolved=False,
            mappings=(),
            unmatched_fixture_ids=(),
        )

    return _build_plan_from_mappings(
        group,
        resolved_windows[0],
    )
