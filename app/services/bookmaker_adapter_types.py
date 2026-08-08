from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class BookmakerQuote:
    bookmaker_code: str
    fixture_id: int
    market: str
    selection: str
    decimal_odds: float
    captured_at: datetime
    source_reference: Optional[str] = None


@dataclass(frozen=True)
class BookmakerAdapterResult:
    bookmaker_code: str
    quote_count: int
    quotes: tuple[BookmakerQuote, ...]
    message: str
