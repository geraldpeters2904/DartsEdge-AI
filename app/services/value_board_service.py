from datetime import date

from app.models.odds_snapshot import OddsSnapshot
from app.services.fixture_service import get_scheduled_fixtures
from app.services.opportunity_ranking_service import _value_metrics
from app.services.prediction_context_service import (
    build_prediction_context,
    context_to_opportunity,
)


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

    # Highest model probability first for now.
    rows.sort(
    key=lambda row: (row["fixture_date"], -row["probability"])
)

    return rows