from __future__ import annotations

from datetime import date
from typing import Iterable


def fetch_current_modus_matches(
    window_start: date,
    window_end: date,
) -> Iterable[object]:
    """
    Current-series MODUS fetch hook.

    This placeholder is intentionally non-destructive. The actual
    current-series collector will be plugged in after the historical
    backfill completes and we inspect the current MODUS page/collector
    output contract.

    Return Match-like objects with at least:
      - date
      - tournament
      - player_a
      - player_b
      - status

    Optional:
      - stage
      - match_format
      - winner
      - score_a
      - score_b
      - provider_id
    """

    return []
