import csv
import io
from datetime import datetime

from fastapi import APIRouter, File, Request, UploadFile
from app.templates_config import templates

from app.db import SessionLocal
from app.models.match import Match
from app.models.match_player_stats import MatchPlayerStats
from app.models.player import Player
from app.services.elo_service import update_elo
from app.services.stats_service import update_player_stats


router = APIRouter()


@router.get("/import")
def import_page(request: Request):
    return templates.TemplateResponse(
        "import.html",
        {
            "request": request,
        },
    )


@router.post("/import-matches")
async def import_matches(file: UploadFile = File(...)):
    contents = await file.read()
    decoded = contents.decode("utf-8")
    reader = csv.DictReader(io.StringIO(decoded))

    db = SessionLocal()
    imported = 0
    skipped = 0

    try:
        for row in reader:
            player_a = db.query(Player).filter(
                Player.name == row["player_a"]
            ).first()

            player_b = db.query(Player).filter(
                Player.name == row["player_b"]
            ).first()

            if not player_a or not player_b:
                skipped += 1
                continue

            match_date = datetime.strptime(
                row["date"],
                "%Y-%m-%d",
            ).date()

            existing_match = db.query(Match).filter(
                Match.date == match_date,
                Match.player_a == row["player_a"],
                Match.player_b == row["player_b"],
                Match.winner == row["winner"],
                Match.score == row["score"],
            ).first()

            if existing_match:
                skipped += 1
                continue

            match = Match(
                date=match_date,
                tournament=row.get("tournament", "MODUS"),
                stage=row.get("stage", "Group"),
                match_format=row.get("match_format", "Best of 7"),
                player_a=row["player_a"],
                player_b=row["player_b"],
                winner=row["winner"],
                score=row["score"],
                first_180_player=row.get("first_180_player"),
                first_leg_winner=row.get("first_leg_winner"),
            )

            db.add(match)
            db.flush()

            db.add(
                MatchPlayerStats(
                    match_id=match.id,
                    player_name=row["player_a"],
                    one80s=int(row.get("player_a_180s", 0)),
                    average=float(row.get("player_a_average", 0)),
                    checkout=float(row.get("player_a_checkout", 0)),
                    first9_average=float(row.get("player_a_first9", 0)),
                    highest_checkout=int(
                        row.get("player_a_highest_checkout", 0)
                    ),
                )
            )

            db.add(
                MatchPlayerStats(
                    match_id=match.id,
                    player_name=row["player_b"],
                    one80s=int(row.get("player_b_180s", 0)),
                    average=float(row.get("player_b_average", 0)),
                    checkout=float(row.get("player_b_checkout", 0)),
                    first9_average=float(row.get("player_b_first9", 0)),
                    highest_checkout=int(
                        row.get("player_b_highest_checkout", 0)
                    ),
                )
            )

            update_elo(player_a, player_b, row["winner"])

            update_player_stats(
                db,
                player_a,
                player_b,
                row["winner"],
                row["score"],
            )

            imported += 1

        db.commit()

        return {
            "message": "Import complete",
            "imported": imported,
            "skipped": skipped,
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()