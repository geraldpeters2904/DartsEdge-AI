from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.odds_snapshot import OddsSnapshot
from app.models.player import Player

DEMO_TOURNAMENT_PREFIX = "DEMO"
DEMO_PROVIDER_ID = "demo-data"
DEMO_PLAYER_PREFIX = "Demo "

_PLAYER_SEEDS = [
    ("Demo Archer", 1588, 91.4, 38.2, 0.34),
    ("Demo Barker", 1532, 88.6, 35.1, 0.27),
    ("Demo Carter", 1610, 93.1, 40.4, 0.38),
    ("Demo Dalton", 1498, 86.8, 33.5, 0.23),
    ("Demo Ellis", 1560, 90.2, 36.8, 0.31),
    ("Demo Foster", 1515, 87.9, 34.4, 0.25),
    ("Demo Grant", 1640, 94.6, 42.1, 0.41),
    ("Demo Hayes", 1544, 89.5, 37.0, 0.29),
]

_FIXTURES = [
    (0, "Demo Archer", "Demo Barker"),
    (0, "Demo Carter", "Demo Dalton"),
    (1, "Demo Ellis", "Demo Foster"),
    (1, "Demo Grant", "Demo Hayes"),
    (2, "Demo Archer", "Demo Carter"),
    (2, "Demo Barker", "Demo Ellis"),
    (3, "Demo Dalton", "Demo Grant"),
    (3, "Demo Foster", "Demo Hayes"),
    (4, "Demo Archer", "Demo Ellis"),
    (4, "Demo Carter", "Demo Grant"),
    (5, "Demo Barker", "Demo Foster"),
    (5, "Demo Dalton", "Demo Hayes"),
    (6, "Demo Archer", "Demo Grant"),
    (6, "Demo Carter", "Demo Hayes"),
]


def _fingerprint(fixture_date: date, player_a: str, player_b: str, selection: str, bookmaker: str, odds: float) -> str:
    raw = f"{fixture_date}|{player_a}|{player_b}|match_winner|{selection}|{bookmaker}|{odds:.2f}|{DEMO_PROVIDER_ID}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def demo_summary(db: Session) -> Dict[str, int]:
    return {
        "players": db.query(Player).filter(Player.name.like(f"{DEMO_PLAYER_PREFIX}%")).count(),
        "fixtures": db.query(Match).filter(Match.tournament.like(f"{DEMO_TOURNAMENT_PREFIX}%")).count(),
        "odds": db.query(OddsSnapshot).filter(OddsSnapshot.provider_id == DEMO_PROVIDER_ID).count(),
    }


def load_demo_data(db: Session) -> Dict[str, int]:
    created_players = 0
    created_fixtures = 0
    created_odds = 0

    for name, elo, average, checkout, one80_rate in _PLAYER_SEEDS:
        player = db.query(Player).filter(Player.name == name).first()
        if player is None:
            db.add(Player(name=name, elo=elo, average=average, checkout=checkout, one80_rate=one80_rate))
            created_players += 1
    db.flush()

    today = date.today()
    for offset, player_a, player_b in _FIXTURES:
        fixture_date = today + timedelta(days=offset)
        fixture = (
            db.query(Match)
            .filter(
                Match.date == fixture_date,
                Match.player_a == player_a,
                Match.player_b == player_b,
                Match.tournament == "DEMO Showcase",
            )
            .first()
        )
        if fixture is None:
            fixture = Match(
                date=fixture_date,
                tournament="DEMO Showcase",
                stage=f"Session {offset + 1}",
                match_format="Best of 7",
                status="scheduled",
                player_a=player_a,
                player_b=player_b,
            )
            db.add(fixture)
            created_fixtures += 1

        for index, selection in enumerate((player_a, player_b)):
            base = 1.72 + ((offset + index) % 5) * 0.12
            for bookmaker, adjustment in (("DemoBet", 0.00), ("Sample Sports", 0.08)):
                decimal_odds = round(base + adjustment, 2)
                fingerprint = _fingerprint(fixture_date, player_a, player_b, selection, bookmaker, decimal_odds)
                exists = db.query(OddsSnapshot).filter(OddsSnapshot.fingerprint == fingerprint).first()
                if exists is None:
                    db.add(
                        OddsSnapshot(
                            fixture_date=fixture_date,
                            tournament="DEMO Showcase",
                            player_a=player_a,
                            player_b=player_b,
                            market="match_winner",
                            selection=selection,
                            bookmaker=bookmaker,
                            decimal_odds=decimal_odds,
                            captured_at=datetime.utcnow(),
                            provider_id=DEMO_PROVIDER_ID,
                            external_id=f"demo-{offset}-{index}-{bookmaker.lower().replace(' ', '-')}",
                            fingerprint=fingerprint,
                        )
                    )
                    created_odds += 1

    db.commit()
    return {
        "created_players": created_players,
        "created_fixtures": created_fixtures,
        "created_odds": created_odds,
        **demo_summary(db),
    }


def reset_demo_data(db: Session) -> Dict[str, int]:
    odds_deleted = db.query(OddsSnapshot).filter(OddsSnapshot.provider_id == DEMO_PROVIDER_ID).delete(synchronize_session=False)
    fixtures_deleted = db.query(Match).filter(Match.tournament.like(f"{DEMO_TOURNAMENT_PREFIX}%")).delete(synchronize_session=False)
    players_deleted = db.query(Player).filter(Player.name.like(f"{DEMO_PLAYER_PREFIX}%")).delete(synchronize_session=False)
    db.commit()
    return {
        "players_deleted": players_deleted,
        "fixtures_deleted": fixtures_deleted,
        "odds_deleted": odds_deleted,
        **demo_summary(db),
    }
