import re

from datetime import date

from app.models.odds_snapshot import OddsSnapshot
from app.models.player import Player
from app.models.player_match_performance import PlayerMatchPerformance
from app.services.fixture_service import get_scheduled_fixtures
from app.services.markets_service import (
    one80_markets,
    probability_over,
)
from app.services.opportunity_ranking_service import _value_metrics
from app.services.match_engine import leg_win_probability
from app.services.leg_market_calibration_service import (
    calibrate_handicap_probability,
    calibrate_total_legs_probability,
)
from app.services.simulation_service import (
    handicap_cover_probability,
    simulate_match,
    total_legs_over_probability,
)
from app.services.player_name_service import resolve_player_by_name
from app.services.player_profile_service import get_player_profile
from app.services.prediction_context_service import (
    build_prediction_context,
    context_to_opportunity,
)


def _player_180_expectation(db, player_name):
    player = resolve_player_by_name(
        db,
        player_name,
        record_alias=False,
    )

    if player is None:
        return None

    performances = (
        db.query(PlayerMatchPerformance)
        .filter(
            PlayerMatchPerformance.player_id == player.id,
            PlayerMatchPerformance.scores_180.isnot(None),
        )
        .all()
    )

    values = [
        int(performance.scores_180)
        for performance in performances
    ]

    if not values:
        return None

    total_180s = sum(values)
    matches = len(values)

    return {
        "matches": matches,
        "total_180s": total_180s,
        "expected": total_180s / matches,
    }


def _current_player_total_180_line(rows, player_name):
    prefix = f"{player_name} | "
    grouped = {}

    for row in rows:
        selection = str(
            getattr(row, "selection", "")
            or ""
        )

        if not selection.startswith(prefix):
            continue

        match = re.search(
            r"\(([+-]?\d+(?:\.\d+)?)\)",
            selection,
        )
        if match is None:
            continue

        line = abs(float(match.group(1)))

        group = grouped.setdefault(
            line,
            {
                "line": line,
                "over": None,
                "under": None,
                "latest": None,
            },
        )

        captured_at = getattr(
            row,
            "captured_at",
            None,
        )
        row_id = getattr(
            row,
            "id",
            0,
        ) or 0

        ordering = (
            captured_at,
            row_id,
        )

        if (
            group["latest"] is None
            or ordering > group["latest"]
        ):
            group["latest"] = ordering

        if " | Over " in selection:
            current = group["over"]
            if (
                current is None
                or ordering
                > current[0]
            ):
                group["over"] = (
                    ordering,
                    float(
                        row.decimal_odds
                    ),
                )

        elif " | Under " in selection:
            current = group["under"]
            if (
                current is None
                or ordering
                > current[0]
            ):
                group["under"] = (
                    ordering,
                    float(
                        row.decimal_odds
                    ),
                )

    complete = [
        group
        for group in grouped.values()
        if (
            group["over"] is not None
            and group["under"] is not None
        )
    ]

    if not complete:
        return None

    current = max(
        complete,
        key=lambda group: group["latest"],
    )

    return {
        "line": current["line"],
        "over_odds": current["over"][1],
        "under_odds": current["under"][1],
    }



def _current_handicap_market(
    rows,
    player_a_name,
    player_b_name,
):
    grouped = {}

    for row in rows:
        selection = str(
            getattr(row, "selection", "")
            or ""
        )

        match = re.match(
            r"^(.*) ([+-]\d+(?:\.\d+)?)$",
            selection,
        )
        if match is None:
            continue

        player_name = match.group(1)
        line = float(match.group(2))

        if player_name not in {
            player_a_name,
            player_b_name,
        }:
            continue

        captured_at = getattr(
            row,
            "captured_at",
            None,
        )
        row_id = getattr(
            row,
            "id",
            0,
        ) or 0
        ordering = (
            captured_at,
            row_id,
        )

        absolute_line = abs(line)
        group = grouped.setdefault(
            absolute_line,
            {
                "player_a": None,
                "player_b": None,
                "latest": None,
            },
        )

        if (
            group["latest"] is None
            or ordering > group["latest"]
        ):
            group["latest"] = ordering

        key = (
            "player_a"
            if player_name == player_a_name
            else "player_b"
        )

        current = group[key]
        if (
            current is None
            or ordering > current[0]
        ):
            group[key] = (
                ordering,
                line,
                float(row.decimal_odds),
            )

    complete = []

    for group in grouped.values():
        player_a = group["player_a"]
        player_b = group["player_b"]

        if (
            player_a is None
            or player_b is None
        ):
            continue

        if player_a[1] != -player_b[1]:
            continue

        complete.append(group)

    if not complete:
        return None

    current = min(
        complete,
        key=lambda group: group["latest"],
    )

    return {
        "player_a_line": current["player_a"][1],
        "player_a_odds": current["player_a"][2],
        "player_b_line": current["player_b"][1],
        "player_b_odds": current["player_b"][2],
    }


def _current_total_legs_line(rows):
    grouped = {}

    for row in rows:
        selection = str(
            getattr(row, "selection", "")
            or ""
        )

        match = re.match(
            r"^(Over|Under) \(\+([0-9]+(?:\.[0-9]+)?)\)$",
            selection,
        )
        if match is None:
            continue

        side = match.group(1).lower()
        line = float(match.group(2))
        captured_at = getattr(
            row,
            "captured_at",
            None,
        )
        row_id = getattr(
            row,
            "id",
            0,
        ) or 0
        ordering = (
            captured_at,
            row_id,
        )

        group = grouped.setdefault(
            line,
            {
                "line": line,
                "over": None,
                "under": None,
                "latest": None,
            },
        )

        if (
            group["latest"] is None
            or ordering > group["latest"]
        ):
            group["latest"] = ordering

        current = group[side]
        if (
            current is None
            or ordering > current[0]
        ):
            group[side] = (
                ordering,
                float(row.decimal_odds),
            )

    complete = [
        group
        for group in grouped.values()
        if (
            group["over"] is not None
            and group["under"] is not None
        )
    ]

    if not complete:
        return None

    current = min(
        complete,
        key=lambda group: group["latest"],
    )

    return {
        "line": current["line"],
        "over_odds": current["over"][1],
        "under_odds": current["under"][1],
    }

def _current_total_180_line(rows):
    grouped = {}

    for row in rows:
        selection = str(
            getattr(row, "selection", "")
            or ""
        )

        match = re.match(
            r"^(Over|Under) \(\+([0-9]+(?:\.[0-9]+)?)\)$",
            selection,
        )
        if match is None:
            continue

        side = match.group(1).lower()
        line = float(match.group(2))

        timestamp = getattr(
            row,
            "captured_at",
            None,
        )
        row_id = getattr(
            row,
            "id",
            0,
        )

        grouped.setdefault(
            line,
            {},
        )[side] = (
            timestamp,
            row_id,
            float(row.decimal_odds),
        )

    complete = []

    for line, sides in grouped.items():
        if (
            "over" not in sides
            or "under" not in sides
        ):
            continue

        newest = max(
            sides["over"][:2],
            sides["under"][:2],
        )

        complete.append(
            (
                newest,
                line,
                sides,
            )
        )

    if not complete:
        return None

    _, line, sides = max(
        complete,
        key=lambda item: item[0],
    )

    return {
        "line": line,
        "over_odds": sides["over"][2],
        "under_odds": sides["under"][2],
    }


def _current_most_180_market(
    rows,
    player_a_name,
    player_b_name,
):
    grouped = {}

    for row in rows:
        selection = str(
            getattr(row, "selection", "")
            or ""
        )

        if selection not in {
            player_a_name,
            "Draw",
            player_b_name,
        }:
            continue

        captured_at = getattr(
            row,
            "captured_at",
            None,
        )
        row_id = getattr(
            row,
            "id",
            0,
        ) or 0

        key = captured_at

        group = grouped.setdefault(
            key,
            {},
        )

        current = group.get(selection)
        ordering = (
            captured_at,
            row_id,
        )

        if (
            current is None
            or ordering > current[0]
        ):
            group[selection] = (
                ordering,
                float(row.decimal_odds),
            )

    complete = []

    for captured_at, selections in grouped.items():
        if not all(
            selection in selections
            for selection in (
                player_a_name,
                "Draw",
                player_b_name,
            )
        ):
            continue

        newest = max(
            selections[player_a_name][0],
            selections["Draw"][0],
            selections[player_b_name][0],
        )

        complete.append(
            (
                newest,
                selections,
            )
        )

    if not complete:
        return None

    _, selections = min(
        complete,
        key=lambda item: item[0],
    )

    return {
        "player_a_odds": selections[
            player_a_name
        ][1],
        "draw_odds": selections[
            "Draw"
        ][1],
        "player_b_odds": selections[
            player_b_name
        ][1],
    }



def _best_of_from_match_format(match_format):
    match = re.search(
        r"Best of (\d+)",
        str(match_format or ""),
        re.IGNORECASE,
    )
    if match is None:
        return None

    best_of = int(match.group(1))
    if best_of <= 0 or best_of % 2 == 0:
        return None

    return best_of


def _match_leg_simulation(db, fixture):
    profile_a = get_player_profile(
        db,
        fixture.player_a,
    )
    profile_b = get_player_profile(
        db,
        fixture.player_b,
    )

    if profile_a is None or profile_b is None:
        return None

    if fixture.date is not None:
        for profile in (profile_a, profile_b):
            latest_match_date = profile.get("latest_match_date")
            if latest_match_date:
                latest_match_date = date.fromisoformat(
                    latest_match_date
                )
                if (
                    fixture.date - latest_match_date
                ).days > 180:
                    return None

    average_a = profile_a.get("average")
    checkout_a = profile_a.get("checkout")
    average_b = profile_b.get("average")
    checkout_b = profile_b.get("checkout")

    required = (
        average_a,
        checkout_a,
        average_b,
        checkout_b,
    )

    if any(
        value is None or float(value) <= 0.0
        for value in required
    ):
        return None

    best_of = _best_of_from_match_format(
        fixture.match_format
    )
    if best_of is None:
        return None

    player_a = Player(
        name=fixture.player_a,
        average=float(average_a),
        checkout=float(checkout_a),
    )
    player_b = Player(
        name=fixture.player_b,
        average=float(average_b),
        checkout=float(checkout_b),
    )

    leg_probability = leg_win_probability(
        player_a,
        player_b,
    )

    return simulate_match(
        {
            "elo": float(
                profile_a.get("elo")
                or 1500.0
            )
        },
        {
            "elo": float(
                profile_b.get("elo")
                or 1500.0
            )
        },
        leg_win_prob_a=leg_probability,
        best_of=best_of,
    )


def _handicap_rows(db, fixture):
    price_rows = (
        db.query(OddsSnapshot)
        .filter(
            OddsSnapshot.fixture_id == fixture.id,
            OddsSnapshot.bookmaker_code == "paddypower",
            OddsSnapshot.market == "handicap",
        )
        .all()
    )

    current = _current_handicap_market(
        price_rows,
        fixture.player_a,
        fixture.player_b,
    )
    if current is None:
        return []

    simulation = _match_leg_simulation(
        db,
        fixture,
    )
    if simulation is None:
        return []

    outcomes = [
        (
            fixture.player_a,
            "a",
            float(current["player_a_line"]),
            float(current["player_a_odds"]),
        ),
        (
            fixture.player_b,
            "b",
            float(current["player_b_line"]),
            float(current["player_b_odds"]),
        ),
    ]

    rows = []

    for player_name, player_side, line, market_odds in outcomes:
        probability_decimal = handicap_cover_probability(
            simulation,
            player=player_side,
            line=line,
        )

        if (
            player_side == "a"
            and line == -1.5
        ):
            probability_decimal = (
                calibrate_handicap_probability(
                    probability_decimal
                )
            )
        elif (
            player_side == "b"
            and line == 1.5
        ):
            player_a_probability = (
                handicap_cover_probability(
                    simulation,
                    player="a",
                    line=-1.5,
                )
            )
            probability_decimal = (
                1.0
                - calibrate_handicap_probability(
                    player_a_probability
                )
            )
        probability = probability_decimal * 100.0

        fair_odds = (
            1.0 / probability_decimal
            if probability_decimal > 0
            else 0.0
        )

        value = _value_metrics(
            probability,
            fair_odds,
            market_odds,
        )

        rows.append(
            {
                "fixture_id": fixture.id,
                "fixture_date": fixture.date,
                "tournament": fixture.tournament,
                "stage": fixture.stage,
                "match_format": fixture.match_format,
                "player_a": fixture.player_a,
                "player_b": fixture.player_b,
                "match": (
                    f"{fixture.player_a} vs "
                    f"{fixture.player_b}"
                ),
                "market": "Leg Handicap",
                "selection": (
                    f"{player_name} {line:+g}"
                ),
                "opponent": (
                    fixture.player_b
                    if player_name == fixture.player_a
                    else fixture.player_a
                ),
                "probability": round(
                    probability,
                    2,
                ),
                "fair_odds": round(
                    fair_odds,
                    2,
                ),
                "market_odds": value[
                    "market_odds"
                ],
                "bookmaker": "Paddy Power",
                "edge": value[
                    "edge_percent"
                ],
                "expected_value_percent": value.get(
                    "expected_value_percent"
                ),
                "is_value_confirmed": value[
                    "is_value_confirmed"
                ],
                "status": value[
                    "status"
                ],
                "status_tone": value[
                    "status_tone"
                ],
                "action": (
                    "Consider"
                    if value["is_value_confirmed"]
                    else "Pass"
                ),
            }
        )

    return rows


def _total_legs_rows(db, fixture):
    price_rows = (
        db.query(OddsSnapshot)
        .filter(
            OddsSnapshot.fixture_id == fixture.id,
            OddsSnapshot.bookmaker_code == "paddypower",
            OddsSnapshot.market == "total_legs",
        )
        .all()
    )

    current = _current_total_legs_line(
        price_rows,
    )
    if current is None:
        return []

    simulation = _match_leg_simulation(
        db,
        fixture,
    )
    if simulation is None:
        return []

    line = float(current["line"])

    over_probability_decimal = (
        total_legs_over_probability(
            simulation,
            line=line,
        )
    )
    if line == 5.5:
        over_probability_decimal = (
            calibrate_total_legs_probability(
                over_probability_decimal
            )
        )

    under_probability_decimal = (
        1.0 - over_probability_decimal
    )

    outcomes = [
        (
            "Over",
            over_probability_decimal,
            float(current["over_odds"]),
        ),
        (
            "Under",
            under_probability_decimal,
            float(current["under_odds"]),
        ),
    ]

    rows = []

    for side, probability_decimal, market_odds in outcomes:
        probability = probability_decimal * 100.0

        fair_odds = (
            1.0 / probability_decimal
            if probability_decimal > 0
            else 0.0
        )

        value = _value_metrics(
            probability,
            fair_odds,
            market_odds,
        )

        rows.append(
            {
                "fixture_id": fixture.id,
                "fixture_date": fixture.date,
                "tournament": fixture.tournament,
                "stage": fixture.stage,
                "match_format": fixture.match_format,
                "player_a": fixture.player_a,
                "player_b": fixture.player_b,
                "match": (
                    f"{fixture.player_a} vs "
                    f"{fixture.player_b}"
                ),
                "market": "Total Legs",
                "selection": (
                    f"{side} {line:g} Total Legs"
                ),
                "opponent": None,
                "probability": round(
                    probability,
                    2,
                ),
                "fair_odds": round(
                    fair_odds,
                    2,
                ),
                "market_odds": value[
                    "market_odds"
                ],
                "bookmaker": "Paddy Power",
                "edge": value[
                    "edge_percent"
                ],
                "expected_value_percent": value.get(
                    "expected_value_percent"
                ),
                "is_value_confirmed": value[
                    "is_value_confirmed"
                ],
                "status": value[
                    "status"
                ],
                "status_tone": value[
                    "status_tone"
                ],
                "action": (
                    "Consider"
                    if value["is_value_confirmed"]
                    else "Pass"
                ),
            }
        )

    return rows

def _most_180_rows(db, fixture):
    player_a_expectation = _player_180_expectation(
        db,
        fixture.player_a,
    )
    player_b_expectation = _player_180_expectation(
        db,
        fixture.player_b,
    )

    if (
        player_a_expectation is None
        or player_b_expectation is None
    ):
        return []

    price_rows = (
        db.query(OddsSnapshot)
        .filter(
            OddsSnapshot.fixture_id == fixture.id,
            OddsSnapshot.bookmaker_code == "paddypower",
            OddsSnapshot.market == "most_180s",
        )
        .all()
    )

    current = _current_most_180_market(
        price_rows,
        fixture.player_a,
        fixture.player_b,
    )

    if current is None:
        return []

    markets = one80_markets(
        player_a_expectation["expected"],
        player_b_expectation["expected"],
    )

    if not markets["most_180s_data_available"]:
        return []

    outcomes = [
        (
            f"{fixture.player_a} Most 180s",
            float(markets["most_180s_a"]),
            float(current["player_a_odds"]),
        ),
        (
            "Draw Most 180s",
            float(markets["most_180s_draw"]),
            float(current["draw_odds"]),
        ),
        (
            f"{fixture.player_b} Most 180s",
            float(markets["most_180s_b"]),
            float(current["player_b_odds"]),
        ),
    ]

    rows = []

    for selection, probability_decimal, market_odds in outcomes:
        probability = probability_decimal * 100.0

        fair_odds = (
            1.0 / probability_decimal
            if probability_decimal > 0
            else 0.0
        )

        value = _value_metrics(
            probability,
            fair_odds,
            market_odds,
        )

        rows.append(
            {
                "fixture_id": fixture.id,
                "fixture_date": fixture.date,
                "tournament": fixture.tournament,
                "stage": fixture.stage,
                "match_format": fixture.match_format,
                "player_a": fixture.player_a,
                "player_b": fixture.player_b,
                "match": (
                    f"{fixture.player_a} vs "
                    f"{fixture.player_b}"
                ),
                "market": "Most 180s",
                "selection": selection,
                "opponent": None,
                "probability": round(
                    probability,
                    2,
                ),
                "fair_odds": round(
                    fair_odds,
                    2,
                ),
                "market_odds": value[
                    "market_odds"
                ],
                "bookmaker": "Paddy Power",
                "edge": value[
                    "edge_percent"
                ],
                "expected_value_percent": value.get(
                    "expected_value_percent"
                ),
                "is_value_confirmed": value[
                    "is_value_confirmed"
                ],
                "status": value[
                    "status"
                ],
                "status_tone": value[
                    "status_tone"
                ],
                "action": (
                    "Consider"
                    if value["is_value_confirmed"]
                    else "Pass"
                ),
                "player_a_history_matches": (
                    player_a_expectation["matches"]
                ),
                "player_b_history_matches": (
                    player_b_expectation["matches"]
                ),
                "player_a_expected_180s": round(
                    float(
                        player_a_expectation["expected"]
                    ),
                    3,
                ),
                "player_b_expected_180s": round(
                    float(
                        player_b_expectation["expected"]
                    ),
                    3,
                ),
            }
        )

    return rows


def _total_180_rows(db, fixture):
    player_a_expectation = _player_180_expectation(
        db,
        fixture.player_a,
    )
    player_b_expectation = _player_180_expectation(
        db,
        fixture.player_b,
    )

    if (
        player_a_expectation is None
        or player_b_expectation is None
    ):
        return []

    price_rows = (
        db.query(OddsSnapshot)
        .filter(
            OddsSnapshot.fixture_id == fixture.id,
            OddsSnapshot.bookmaker_code == "paddypower",
            OddsSnapshot.market == "total_180s",
        )
        .all()
    )

    current = _current_total_180_line(
        price_rows,
    )

    if current is None:
        return []

    line = float(current["line"])
    expected = (
        float(player_a_expectation["expected"])
        + float(player_b_expectation["expected"])
    )

    over_probability_decimal = probability_over(
        line,
        expected,
    )
    under_probability_decimal = (
        1.0 - over_probability_decimal
    )

    sides = [
        (
            "Over",
            over_probability_decimal,
            float(current["over_odds"]),
        ),
        (
            "Under",
            under_probability_decimal,
            float(current["under_odds"]),
        ),
    ]

    rows = []

    for side, probability_decimal, market_odds in sides:
        probability = probability_decimal * 100.0

        fair_odds = (
            1.0 / probability_decimal
            if probability_decimal > 0
            else 0.0
        )

        value = _value_metrics(
            probability,
            fair_odds,
            market_odds,
        )

        rows.append(
            {
                "fixture_id": fixture.id,
                "fixture_date": fixture.date,
                "tournament": fixture.tournament,
                "stage": fixture.stage,
                "match_format": fixture.match_format,
                "player_a": fixture.player_a,
                "player_b": fixture.player_b,
                "match": (
                    f"{fixture.player_a} vs "
                    f"{fixture.player_b}"
                ),
                "market": "Total 180s",
                "selection": (
                    f"{side} {line:g} Total 180s"
                ),
                "opponent": None,
                "probability": round(
                    probability,
                    2,
                ),
                "fair_odds": round(
                    fair_odds,
                    2,
                ),
                "market_odds": value[
                    "market_odds"
                ],
                "bookmaker": "Paddy Power",
                "edge": value[
                    "edge_percent"
                ],
                "expected_value_percent": value.get(
                    "expected_value_percent"
                ),
                "is_value_confirmed": value[
                    "is_value_confirmed"
                ],
                "status": value[
                    "status"
                ],
                "status_tone": value[
                    "status_tone"
                ],
                "action": (
                    "Consider"
                    if value["is_value_confirmed"]
                    else "Pass"
                ),
                "player_a_history_matches": (
                    player_a_expectation["matches"]
                ),
                "player_b_history_matches": (
                    player_b_expectation["matches"]
                ),
                "expected_180s": round(
                    expected,
                    3,
                ),
            }
        )

    return rows

def _player_total_180_rows(db, fixture, player_name):
    expectation = _player_180_expectation(
        db,
        player_name,
    )

    if expectation is None:
        return []

    price_rows = (
        db.query(OddsSnapshot)
        .filter(
            OddsSnapshot.fixture_id == fixture.id,
            OddsSnapshot.bookmaker_code == "paddypower",
            OddsSnapshot.market == "player_total_180s",
        )
        .all()
    )

    current = _current_player_total_180_line(
        price_rows,
        player_name,
    )

    if current is None:
        return []

    line = float(current["line"])
    expected = float(expectation["expected"])

    over_probability_decimal = probability_over(
        line,
        expected,
    )
    under_probability_decimal = (
        1.0 - over_probability_decimal
    )

    sides = [
        (
            "Over",
            over_probability_decimal,
            float(current["over_odds"]),
        ),
        (
            "Under",
            under_probability_decimal,
            float(current["under_odds"]),
        ),
    ]

    rows = []

    for side, probability_decimal, market_odds in sides:
        probability = probability_decimal * 100.0
        fair_odds = (
            1.0 / probability_decimal
            if probability_decimal > 0
            else 0.0
        )

        value = _value_metrics(
            probability,
            fair_odds,
            market_odds,
        )

        rows.append(
            {
                "fixture_id": fixture.id,
                "fixture_date": fixture.date,
                "tournament": fixture.tournament,
                "stage": fixture.stage,
                "match_format": fixture.match_format,
                "player_a": fixture.player_a,
                "player_b": fixture.player_b,
                "match": (
                    f"{fixture.player_a} vs "
                    f"{fixture.player_b}"
                ),
                "market": "Player Total 180s",
                "selection": (
                    f"{player_name} "
                    f"{side} {line:g} 180s"
                ),
                "opponent": (
                    fixture.player_b
                    if player_name == fixture.player_a
                    else fixture.player_a
                ),
                "probability": round(
                    probability,
                    2,
                ),
                "fair_odds": round(
                    fair_odds,
                    2,
                ),
                "market_odds": value[
                    "market_odds"
                ],
                "bookmaker": "Paddy Power",
                "edge": value[
                    "edge_percent"
                ],
                "expected_value_percent": value.get(
                    "expected_value_percent"
                ),
                "is_value_confirmed": value[
                    "is_value_confirmed"
                ],
                "status": value[
                    "status"
                ],
                "status_tone": value[
                    "status_tone"
                ],
                "action": (
                    "Consider"
                    if value["is_value_confirmed"]
                    else "Pass"
                ),
                "history_matches": expectation[
                    "matches"
                ],
                "expected_180s": round(
                    expected,
                    3,
                ),
            }
        )

    return rows


def build_value_board(db):
    fixtures = get_scheduled_fixtures(db)
    rows = []

    for fixture in fixtures:

        try:
            context = build_prediction_context(
                db,
                fixture.id,
            )
        except (
            LookupError,
            RuntimeError,
            TypeError,
            ValueError,
        ):
            continue

        opportunity = context_to_opportunity(
            context,
            fixture_date=fixture.date,
            tournament=fixture.tournament,
        )

        selection = opportunity["selection"]
        selected_probability = float(
            opportunity["probability"]
        )
        fair_odds = opportunity["fair_odds"]

        if selection == fixture.player_a:
            opponent = fixture.player_b
        else:
            opponent = fixture.player_a

        price = (
            db.query(OddsSnapshot)
            .filter(
                OddsSnapshot.fixture_id == fixture.id,
                OddsSnapshot.bookmaker_code == "paddypower",
                OddsSnapshot.market == "match_winner",
                OddsSnapshot.selection == selection,
            )
            .order_by(
                OddsSnapshot.captured_at.desc(),
                OddsSnapshot.id.desc(),
            )
            .first()
        )

        market_odds = (
            float(price.decimal_odds)
            if price is not None
            else None
        )

        value = _value_metrics(
            selected_probability,
            fair_odds,
            market_odds,
        )

        rows.append(
            {
                "fixture_id": fixture.id,
                "fixture_date": fixture.date,
                "tournament": fixture.tournament,
                "stage": fixture.stage,
                "match_format": fixture.match_format,
                "player_a": fixture.player_a,
                "player_b": fixture.player_b,
                "match": (
                    f"{fixture.player_a} vs "
                    f"{fixture.player_b}"
                ),
                "market": "Match Winner",
                "selection": selection,
                "opponent": opponent,
                "probability": selected_probability,
                "fair_odds": fair_odds,
                "market_odds": value["market_odds"],
                "bookmaker": (
                    "Paddy Power"
                    if price is not None
                    else None
                ),
                "edge": value["edge_percent"],
                "expected_value_percent": value.get(
                    "expected_value_percent"
                ),
                "is_value_confirmed": value[
                    "is_value_confirmed"
                ],
                "status": value["status"],
                "status_tone": value["status_tone"],
                "action": (
                    "Consider"
                    if value["is_value_confirmed"]
                    else (
                        "Awaiting Odds"
                        if value["market_odds"] is None
                        else "Pass"
                    )
                ),
            }
        )

        rows.extend(
            _player_total_180_rows(
                db,
                fixture,
                fixture.player_a,
            )
        )
        rows.extend(
            _player_total_180_rows(
                db,
                fixture,
                fixture.player_b,
            )
        )

        rows.extend(
            _total_180_rows(
                db,
                fixture,
            )
        )

        rows.extend(
            _most_180_rows(
                db,
                fixture,
            )
        )

        rows.extend(
            _handicap_rows(
                db,
                fixture,
            )
        )

        rows.extend(
            _total_legs_rows(
                db,
                fixture,
            )
        )


    rows.sort(
        key=lambda row: (
            row["fixture_date"],
            0 if row["is_value_confirmed"] else 1,
            -(
                row["expected_value_percent"]
                if row["expected_value_percent"] is not None
                else float("-inf")
            ),
            -row["probability"],
        )
    )

    return rows
