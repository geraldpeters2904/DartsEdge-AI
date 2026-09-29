from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.services.modus_stale_reconciliation_plan_service import (
    StaleReconciliationPlan,
)
from app.services.modus_stale_scope_grouping_service import (
    StaleFixtureScopeGroup,
)
from app.services.player_name_service import normalise_player_name


@dataclass(frozen=True)
class VerifiedSequenceAnchor:
    fixture_id: int
    real_match_id: int


def _pair_key(player_a: str, player_b: str) -> tuple[str, str]:
    names = (
        normalise_player_name(player_a),
        normalise_player_name(player_b),
    )

    if not all(names):
        return ("", "")

    return tuple(sorted(names))


def _completed_cards_in_order(
    completed_cards: Sequence[object],
) -> tuple[object, ...]:
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


def build_anchor_aware_stale_reconciliation_plan(
    group: StaleFixtureScopeGroup,
    completed_cards: Sequence[object],
    *,
    anchors: Sequence[VerifiedSequenceAnchor],
) -> StaleReconciliationPlan:
    ordered_cards = _completed_cards_in_order(completed_cards)

    if not group.fixtures or not ordered_cards or not anchors:
        return StaleReconciliationPlan(
            resolved=False,
            mappings=(),
            unmatched_fixture_ids=(),
        )

    card_index_by_id = {
        int(card.match_id): index
        for index, card in enumerate(ordered_cards)
    }

    candidate_mappings = []

    for anchor in anchors:
        anchor_index = card_index_by_id.get(
            int(anchor.real_match_id)
        )

        if anchor_index is None:
            continue

        next_index = anchor_index + 1

        if next_index >= len(ordered_cards):
            continue

        next_card = ordered_cards[next_index]

        for fixture in group.fixtures:
            if int(fixture.fixture_id) <= int(anchor.fixture_id):
                continue

            fixture_pair = _pair_key(
                fixture.player_a,
                fixture.player_b,
            )
            card_pair = _pair_key(
                getattr(next_card, "player_a_name", ""),
                getattr(next_card, "player_b_name", ""),
            )

            if fixture_pair != card_pair:
                break

            candidate_mappings.append(
                (
                    int(fixture.fixture_id),
                    int(next_card.match_id),
                )
            )
            break

    unique_mappings = tuple(dict.fromkeys(candidate_mappings))

    if len(unique_mappings) != 1:
        return StaleReconciliationPlan(
            resolved=False,
            mappings=(),
            unmatched_fixture_ids=(),
        )

    mapped_fixture_id = unique_mappings[0][0]

    return StaleReconciliationPlan(
        resolved=True,
        mappings=unique_mappings,
        unmatched_fixture_ids=tuple(
            int(fixture.fixture_id)
            for fixture in group.fixtures
            if int(fixture.fixture_id) != mapped_fixture_id
        ),
    )


def discover_verified_sequence_anchors(
    db,
    group: StaleFixtureScopeGroup,
    completed_cards: Sequence[object],
) -> tuple[VerifiedSequenceAnchor, ...]:
    import re

    from app.models.canonical_data import ProviderEntityMapping
    from app.models.match import Match
    from app.services.modus_import_scope_service import (
        find_modus_import_scope_for_match,
    )

    completed_card_by_id = {
        int(card.match_id): card
        for card in completed_cards
        if getattr(card, "match_id", None) is not None
    }
    completed_card_ids = set(completed_card_by_id)

    if not group.fixtures or not completed_card_ids:
        return ()

    first_stale_fixture_id = min(
        int(fixture.fixture_id)
        for fixture in group.fixtures
    )

    candidate_matches = (
        db.query(Match)
        .filter(
            Match.status == "completed",
            Match.id < first_stale_fixture_id,
        )
        .order_by(Match.id.desc())
        .all()
    )

    anchors = []

    for match in candidate_matches:
        scope = find_modus_import_scope_for_match(
            db,
            int(match.id),
        )
        if scope != group.scope:
            continue

        intervening_matches = (
            db.query(Match)
            .filter(
                Match.id > int(match.id),
                Match.id < first_stale_fixture_id,
            )
            .order_by(Match.id.asc())
            .all()
        )

        if any(
            find_modus_import_scope_for_match(
                db,
                int(intervening.id),
            ) == group.scope
            for intervening in intervening_matches
        ):
            continue

        mappings = (
            db.query(ProviderEntityMapping)
            .filter(
                ProviderEntityMapping.provider == "modus-official",
                ProviderEntityMapping.entity_type == "fixture",
                ProviderEntityMapping.internal_id == int(match.id),
            )
            .order_by(ProviderEntityMapping.id.asc())
            .all()
        )

        verified_ids = []

        for mapping in mappings:
            parsed = re.fullmatch(
                r"modus-match-(\d+)",
                str(mapping.external_id or "").strip(),
            )
            if parsed is None:
                continue

            real_match_id = int(parsed.group(1))
            card = completed_card_by_id.get(real_match_id)
            if card is None:
                continue

            match_pair = _pair_key(
                match.player_a,
                match.player_b,
            )
            card_pair = _pair_key(
                getattr(card, "player_a_name", ""),
                getattr(card, "player_b_name", ""),
            )

            if not match_pair or match_pair == ("", ""):
                continue

            if match_pair != card_pair:
                continue

            verified_ids.append(real_match_id)

        verified_ids = list(dict.fromkeys(verified_ids))

        if len(verified_ids) != 1:
            continue

        anchors.append(
            VerifiedSequenceAnchor(
                fixture_id=int(match.id),
                real_match_id=verified_ids[0],
            )
        )

    return tuple(anchors)
