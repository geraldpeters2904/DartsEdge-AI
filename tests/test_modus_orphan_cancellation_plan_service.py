from datetime import date

from app.services.modus_import_scope_service import ModusImportScope
from app.services.modus_orphan_cancellation_plan_service import (
    build_orphan_cancellation_plan,
)
from app.services.modus_stale_scope_grouping_service import (
    ScopedStaleFixture,
    StaleFixtureScopeGroup,
)


class Card:
    def __init__(
        self,
        match_id,
        match_number,
        player_a_name,
        player_b_name,
    ):
        self.match_id = match_id
        self.match_number = match_number
        self.player_a_name = player_a_name
        self.player_b_name = player_b_name


def _group(*fixtures):
    return StaleFixtureScopeGroup(
        scope=ModusImportScope(
            series_id=26,
            week_id=197,
            group="Group B",
        ),
        fixtures=tuple(fixtures),
    )


def _fixture(
    fixture_id,
    player_a,
    player_b,
):
    return ScopedStaleFixture(
        fixture_id=fixture_id,
        fixture_date=date(2026, 9, 19),
        player_a=player_a,
        player_b=player_b,
        stage="Group B",
    )


def _complete_double_round_robin():
    players = [
        "Alpha",
        "Bravo",
        "Charlie",
        "Delta",
        "Echo",
    ]

    cards = []
    match_number = 1
    match_id = 2000

    for _ in range(2):
        for index, player_a in enumerate(players):
            for player_b in players[index + 1:]:
                cards.append(
                    Card(
                        match_id,
                        match_number,
                        player_a,
                        player_b,
                    )
                )
                match_id += 1
                match_number += 1

    return tuple(cards)


def test_complete_double_round_robin_marks_accounted_pair_candidate():
    group = _group(
        _fixture(
            17855,
            "Richie Howson",
            "Keegan Brown",
        )
    )

    cards = (
        Card(19945, 1, "Keegan Brown", "Richie Howson"),
        Card(19946, 2, "Chas Barstow", "Henry Cooper"),
        Card(19948, 3, "Steve Green", "Keegan Brown"),
        Card(19950, 4, "Richie Howson", "Chas Barstow"),
        Card(19952, 5, "Henry Cooper", "Steve Green"),
        Card(19954, 6, "Keegan Brown", "Chas Barstow"),
        Card(19956, 7, "Richie Howson", "Henry Cooper"),
        Card(19958, 8, "Chas Barstow", "Steve Green"),
        Card(19960, 9, "Henry Cooper", "Keegan Brown"),
        Card(19962, 10, "Steve Green", "Richie Howson"),
        Card(19993, 11, "Richie Howson", "Steve Green"),
        Card(19995, 12, "Keegan Brown", "Henry Cooper"),
        Card(19997, 13, "Steve Green", "Chas Barstow"),
        Card(19999, 14, "Henry Cooper", "Richie Howson"),
        Card(20001, 15, "Chas Barstow", "Keegan Brown"),
        Card(20003, 16, "Steve Green", "Henry Cooper"),
        Card(20005, 17, "Chas Barstow", "Richie Howson"),
        Card(20007, 18, "Keegan Brown", "Steve Green"),
        Card(20009, 19, "Henry Cooper", "Chas Barstow"),
        Card(20011, 20, "Richie Howson", "Keegan Brown"),
    )

    plan = build_orphan_cancellation_plan(
        group,
        cards,
    )

    assert plan.resolved
    assert plan.fixture_ids == (17855,)
    assert "2-round-robin" in plan.reason


def test_incomplete_round_robin_is_rejected():
    cards = _complete_double_round_robin()[:-1]

    plan = build_orphan_cancellation_plan(
        _group(
            _fixture(
                100,
                "Alpha",
                "Bravo",
            )
        ),
        cards,
    )

    assert not plan.resolved
    assert plan.fixture_ids == ()


def test_unbalanced_pair_counts_are_rejected():
    cards = list(_complete_double_round_robin())
    cards[-1] = Card(
        9999,
        20,
        "Alpha",
        "Bravo",
    )

    plan = build_orphan_cancellation_plan(
        _group(
            _fixture(
                100,
                "Alpha",
                "Bravo",
            )
        ),
        tuple(cards),
    )

    assert not plan.resolved
    assert plan.fixture_ids == ()


def test_pair_not_present_in_completed_structure_is_not_candidate():
    cards = _complete_double_round_robin()

    plan = build_orphan_cancellation_plan(
        _group(
            _fixture(
                100,
                "Alpha",
                "Foxtrot",
            )
        ),
        cards,
    )

    assert not plan.resolved
    assert plan.fixture_ids == ()


def test_empty_stale_group_is_rejected():
    plan = build_orphan_cancellation_plan(
        _group(),
        _complete_double_round_robin(),
    )

    assert not plan.resolved
    assert plan.fixture_ids == ()
