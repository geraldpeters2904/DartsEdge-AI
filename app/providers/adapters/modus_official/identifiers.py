from __future__ import annotations

import re
import unicodedata


def _slug(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if not text:
        raise ValueError("Unable to create a stable identifier from a blank value.")
    return text


def modus_match_external_id(match_id: int) -> str:
    match_id = int(match_id)
    if match_id <= 0:
        raise ValueError("match_id must be greater than zero.")
    return f"modus-match-{match_id}"


def modus_player_external_id(player_name: str) -> str:
    return f"modus-player-{_slug(player_name)}"


def modus_source_external_id(
    entity_type: str,
    *,
    match_id: int,
    player_external_id: str | None = None,
) -> str:
    entity_type = _slug(entity_type)
    match_id = int(match_id)
    if match_id <= 0:
        raise ValueError("match_id must be greater than zero.")

    if entity_type == "statistics":
        if not player_external_id:
            raise ValueError(
                "player_external_id is required for statistics source IDs."
            )
        return f"modus:statistics:{match_id}:{_slug(player_external_id)}"

    if entity_type not in {"fixture", "result"}:
        raise ValueError(
            "entity_type must be fixture, result or statistics."
        )

    return f"modus:{entity_type}:{match_id}"
