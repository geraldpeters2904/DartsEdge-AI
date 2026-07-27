from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.canonical.common import SourceReference, StrictCanonicalModel


class CanonicalOddsSnapshot(StrictCanonicalModel):
    """One bookmaker price observed at one point in time."""

    match_external_id: str = Field(min_length=1, max_length=160)
    market: str = Field(min_length=1, max_length=80)
    selection_external_id: Optional[str] = Field(default=None, max_length=160)
    selection_name: str = Field(min_length=1, max_length=180)
    bookmaker: str = Field(min_length=1, max_length=120)
    decimal_odds: float = Field(gt=1.0, le=1000)
    captured_at: datetime
    source: SourceReference
