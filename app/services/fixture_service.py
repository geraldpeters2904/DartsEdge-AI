from datetime import date

from app.models.match import Match
from app.models.player import Player


def get_fixture_form_data(db):
    players = (
        db.query(Player)
        .order_by(Player.name.asc())
        .all()
    )

    return {
        "players": players,
        "today": date.today(),
    }


def get_scheduled_fixtures(db):
    return (
        db.query(Match)
        .filter(Match.status == "scheduled")
        .order_by(Match.date.asc(), Match.id.asc())
        .all()
    )


def create_fixture(
    db,
    fixture_date,
    tournament,
    stage,
    match_format,
    player_a,
    player_b,
):
    if player_a == player_b:
        return {
            "success": False,
            "error": "Please select two different players.",
        }

    player_a_exists = (
        db.query(Player)
        .filter(Player.name == player_a)
        .first()
    )

    player_b_exists = (
        db.query(Player)
        .filter(Player.name == player_b)
        .first()
    )

    if not player_a_exists or not player_b_exists:
        return {
            "success": False,
            "error": "One or both selected players were not found.",
        }

    fixture = Match(
        date=fixture_date,
        tournament=tournament.strip() or "MODUS",
        stage=stage.strip() or "Group",
        match_format=match_format.strip() or "Best of 7",
        status="scheduled",
        player_a=player_a,
        player_b=player_b,
        winner=None,
        score=None,
        first_180_player=None,
        first_leg_winner=None,
    )

    db.add(fixture)
    db.commit()
    db.refresh(fixture)

    return {
        "success": True,
        "fixture": fixture,
    }


def delete_fixture(db, fixture_id):
    fixture = (
        db.query(Match)
        .filter(Match.id == fixture_id)
        .first()
    )

    if not fixture:
        return False

    db.delete(fixture)
    db.commit()

    return True