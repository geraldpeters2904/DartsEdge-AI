from __future__ import annotations

from typing import Any, Sequence, Tuple

from app.services.player_name_service import normalise_player_name


SequenceMapping = Tuple[Tuple[int, int], ...]


def _pair_key(
    player_a: str,
    player_b: str,
) -> tuple[str, str]:
    names = (
        normalise_player_name(player_a),
        normalise_player_name(player_b),
    )

    if not all(names):
        raise ValueError(
            "MODUS sequence reconciliation requires two player names."
        )

    return tuple(sorted(names))


def _completed_cards_in_sequence(
    completed_cards: Sequence[Any],
) -> tuple[Any, ...]:
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


def resolve_unique_modus_sequence(
    stale_fixtures: Sequence[Any],
    completed_cards: Sequence[Any],
) -> SequenceMapping:
    """
    Resolve completed MODUS cards against an ordered stale-fixture block.

    Completed cards must all match, in sequence, against a subsequence of the
    stale fixtures. Stale provisional fixtures may be skipped.

    A mapping is returned only when exactly one complete alignment exists.
    Multiple possible alignments are deliberately treated as ambiguous.
    """
    stale = tuple(stale_fixtures)
    completed = _completed_cards_in_sequence(completed_cards)

    if not stale or not completed:
        return ()

    if len(completed) > len(stale):
        return ()

    stale_pairs = tuple(
        _pair_key(
            getattr(item, "player_a", ""),
            getattr(item, "player_b", ""),
        )
        for item in stale
    )

    completed_pairs = tuple(
        _pair_key(
            getattr(card, "player_a_name", ""),
            getattr(card, "player_b_name", ""),
        )
        for card in completed
    )

    solutions = []

    def search(
        stale_index: int,
        completed_index: int,
        mapping: tuple[tuple[int, int], ...],
    ) -> None:
        if len(solutions) > 1:
            return

        if completed_index == len(completed):
            solutions.append(mapping)
            return

        remaining_stale = len(stale) - stale_index
        remaining_completed = len(completed) - completed_index

        if remaining_stale < remaining_completed:
            return

        target_pair = completed_pairs[completed_index]

        for index in range(
            stale_index,
            len(stale),
        ):
            if len(stale) - index < remaining_completed:
                break

            if stale_pairs[index] != target_pair:
                continue

            fixture_id = int(
                getattr(stale[index], "fixture_id")
            )
            match_id = int(
                getattr(
                    completed[completed_index],
                    "match_id",
                )
            )

            search(
                index + 1,
                completed_index + 1,
                mapping + ((fixture_id, match_id),),
            )

            if len(solutions) > 1:
                return

    search(
        0,
        0,
        (),
    )

    if len(solutions) != 1:
        return ()

    return solutions[0]
