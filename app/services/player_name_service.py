from __future__ import annotations

import re
import unicodedata
from typing import Optional

from app.models.historical_import import PlayerAlias
from app.models.player import Player


_APOSTROPHE_VARIANTS = {
    "\u2018": "'",  # left single quotation mark
    "\u2019": "'",  # right single quotation mark
    "\u02bc": "'",  # modifier letter apostrophe
    "\u00b4": "'",  # acute accent used as apostrophe
    "\u0060": "'",  # grave accent
    "\uff07": "'",  # full-width apostrophe
}

_SPACE_VARIANTS = {
    "\u00a0": " ",
    "\u2007": " ",
    "\u2009": " ",
    "\u202f": " ",
}


def normalise_player_name(value: str) -> str:
    text = str(value or "")

    # Replace punctuation before Unicode normalisation so an acute-accent
    # apostrophe does not become a detached combining mark.
    for old, new in _APOSTROPHE_VARIANTS.items():
        text = text.replace(old, new)

    for old, new in _SPACE_VARIANTS.items():
        text = text.replace(old, new)

    text = unicodedata.normalize("NFKC", text)

    # Be defensive about already-decomposed combining accents.
    text = text.replace("\u0301", "'")
    text = text.replace("_", " ")
    text = re.sub(r"\s*'\s*", "'", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text.casefold()


def player_alias_key(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        normalise_player_name(value),
    )


def resolve_player_by_name(
    db,
    player_name: str,
    *,
    provider: str = "modus-official",
    record_alias: bool = True,
) -> Optional[Player]:
    exact = (
        db.query(Player)
        .filter(Player.name == player_name)
        .first()
    )

    if exact is not None:
        _remember_alias(
            db,
            provider,
            player_name,
            exact,
            record_alias,
        )
        return exact

    key = player_alias_key(player_name)

    if key:
        query = db.query(PlayerAlias)

        # Real SQLAlchemy queries support filter_by. Some focused unit-test
        # doubles only implement filter/first/all, so skip the alias fast path
        # there and continue to the normalised player scan.
        if hasattr(query, "filter_by"):
            alias = (
                query.filter_by(
                    provider=provider,
                    alias_key=key,
                )
                .first()
            )

            if alias is not None:
                player = (
                    db.query(Player)
                    .filter(Player.id == alias.player_id)
                    .first()
                )

                if player is not None:
                    return player

    target = normalise_player_name(player_name)

    if not target:
        return None

    matches = [
        player
        for player in db.query(Player).all()
        if normalise_player_name(player.name) == target
    ]

    if len(matches) != 1:
        return None

    player = matches[0]

    _remember_alias(
        db,
        provider,
        player_name,
        player,
        record_alias,
    )

    return player


def _remember_alias(
    db,
    provider: str,
    source_name: str,
    player: Player,
    enabled: bool,
) -> None:
    if not enabled or not callable(getattr(db, "add", None)):
        return

    key = player_alias_key(source_name)

    if not key:
        return

    query = db.query(PlayerAlias)

    if not hasattr(query, "filter_by"):
        return

    existing = (
        query.filter_by(
            provider=provider,
            alias_key=key,
        )
        .first()
    )

    if existing is not None:
        existing.player_id = player.id
        existing.alias = source_name
        return

    db.add(
        PlayerAlias(
            provider=provider,
            alias=source_name,
            alias_key=key,
            player_id=player.id,
        )
    )
