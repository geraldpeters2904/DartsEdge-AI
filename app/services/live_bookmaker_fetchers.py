from __future__ import annotations

from typing import Iterable

from app.services.paddy_power_live_bridge import (
    fetch_existing_paddy_power_quotes,
)


def fetch_paddy_power_quotes(
) -> Iterable[dict]:
    return (
        fetch_existing_paddy_power_quotes()
    )


def fetch_bet365_quotes(
) -> Iterable[dict]:
    """
    Bet365 remains deliberately disconnected in Sprint 2.4.

    Sprint 2.5 will add the second real source once the Paddy Power
    end-to-end path is proven in production.
    """
    return []
