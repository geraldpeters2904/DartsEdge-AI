from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass(frozen=True)
class CapturedBookmakerPrice:
    fixture_date: date
    tournament: str
    player_a: str
    player_b: str
    market: str
    selection: str
    bookmaker: str
    decimal_odds: float
    captured_at: datetime
    provider_id: Optional[str] = None


@dataclass(frozen=True)
class BookmakerCaptureReport:
    bookmaker: str
    source_url: str
    captured_at: datetime
    extracted_prices: int
    stored_prices: int
    unchanged_prices: int
    skipped_prices: int
    challenge_detected: bool
    message: str
