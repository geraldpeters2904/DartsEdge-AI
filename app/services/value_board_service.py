import re

from datetime import date

from app.models.odds_snapshot import OddsSnapshot
from app.models.player_match_performance import PlayerMatchPerformance
from app.services.fixture_service import get_scheduled_fixtures
from app.services.markets_service import probability_over
from app.services.opportunity_ranking_service import _value_metrics
from app.services.player_name_service import resolve_player_by_name
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
