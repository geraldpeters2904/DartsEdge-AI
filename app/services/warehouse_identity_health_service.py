from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple
from app.models.historical_import import PlayerAlias
from app.models.match import Match
from app.models.player import Player
from app.models.player_match_performance import PlayerMatchPerformance
from app.services.player_name_service import normalise_player_name

@dataclass(frozen=True)
class WarehouseHealthItem:
    label: str
    status: str
    detail: str

@dataclass(frozen=True)
class WarehouseIdentityHealth:
    players: int
    aliases: int
    matches: int
    performances: int
    duplicate_name_groups: int
    completed_matches_missing_performances: int
    items: Tuple[WarehouseHealthItem, ...]

class WarehouseIdentityHealthService:
    def build(self, db):
        players = db.query(Player).all()
        aliases = db.query(PlayerAlias).count()
        matches = db.query(Match).all()
        performances = db.query(PlayerMatchPerformance).count()

        grouped = {}
        for player in players:
            grouped.setdefault(normalise_player_name(player.name), []).append(player)
        duplicate_groups = [v for k, v in grouped.items() if k and len(v) > 1]

        missing = 0
        for match in matches:
            if str(match.status or "").casefold() != "completed":
                continue
            count = db.query(PlayerMatchPerformance).filter(
                PlayerMatchPerformance.match_id == match.id
            ).count()
            if count < 2:
                missing += 1

        items = (
            WarehouseHealthItem(
                "Player identity duplicates",
                "pass" if not duplicate_groups else "warning",
                "No normalised duplicate player names." if not duplicate_groups else f"{len(duplicate_groups)} name group(s) require review.",
            ),
            WarehouseHealthItem(
                "Completed match performances",
                "pass" if missing == 0 else "warning",
                "Every completed match has two performances." if missing == 0 else f"{missing} completed match(es) have fewer than two performances.",
            ),
        )

        return WarehouseIdentityHealth(
            len(players), aliases, len(matches), performances,
            len(duplicate_groups), missing, items
        )
