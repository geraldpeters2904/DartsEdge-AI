from __future__ import annotations

from typing import Iterable


def fetch_paddy_power_quotes(
) -> Iterable[dict]:
    """
    Placeholder live Paddy Power fetcher.

    Sprint 2.3 deliberately separates orchestration from source-specific
    browser/API extraction. Sprint 2.4 will connect this function to the
    existing Paddy Power MODUS capture/extractor service.
    """
    return []


def fetch_bet365_quotes(
) -> Iterable[dict]:
    """
    Placeholder live Bet365 fetcher.

    The collector can already run safely with an empty source while the
    real capture method is implemented separately.
    """
    return []
