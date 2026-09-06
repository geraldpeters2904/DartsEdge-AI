import re

from datetime import date

from app.models.odds_snapshot import OddsSnapshot
from app.services.fixture_service import get_scheduled_fixtures
from app.services.opportunity_ranking_service import _value_metrics
from app.services.prediction_context_service import (
    build_prediction_context,
    context_to_opportunity,
)


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
