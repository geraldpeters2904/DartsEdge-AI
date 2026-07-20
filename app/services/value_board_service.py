from datetime import date

from app.services.fixture_service import get_scheduled_fixtures
from app.services.prediction_pipeline import build_prediction


def build_value_board(db):
    fixtures = get_scheduled_fixtures(db)
    rows = []

    for fixture in fixtures:

        prediction = build_prediction(
            db,
            fixture.player_a,
            fixture.player_b,
        )

        # Skip fixtures where a player cannot be found or predicted.
        if not prediction:
            continue

        selection = prediction["recommendation"]["selection"]

        if selection == fixture.player_a:
            selected_probability = prediction["win_prob_a"]
            opponent = fixture.player_b
        else:
            selected_probability = prediction["win_prob_b"]
            opponent = fixture.player_a

        fair_odds = (
            1 / selected_probability
            if selected_probability > 0
            else None
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
                "probability": selected_probability * 100,
                "fair_odds": fair_odds,
                "market_odds": None,
                "edge": None,
                "action": "Awaiting Odds",
            }
        )

    # Highest model probability first for now.
    rows.sort(
    key=lambda row: (row["fixture_date"], -row["probability"])
)

    return rows