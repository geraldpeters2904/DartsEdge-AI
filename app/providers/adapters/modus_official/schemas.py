from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class ModusMatchListRecord:
    match_id: int
    player_a_name: str
    player_b_name: str
    player_a_legs: Optional[int] = None
    player_b_legs: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    series_label: Optional[str] = None
    week_label: Optional[str] = None
    group: Optional[str] = None
    match_number: Optional[int] = None


@dataclass(frozen=True)
class ModusGroupTableRecord:
    position: int
    player_name: str
    played: int
    won: int
    lost: int
    leg_difference: int
    three_dart_average: float
    points: int


@dataclass(frozen=True)
class ModusResultsPageRecord:
    series_id: int
    series_label: str
    week_id: int
    week_label: str
    group: str
    matches: List[ModusMatchListRecord] = field(default_factory=list)
    group_table: List[ModusGroupTableRecord] = field(default_factory=list)


@dataclass(frozen=True)
class ModusPlayerMatchStats:
    player_name: str
    three_dart_average: Optional[float] = None
    scores_100_plus: Optional[int] = None
    scores_140_plus: Optional[int] = None
    scores_180: Optional[int] = None
    checkout_attempts: Optional[int] = None
    checkouts_completed: Optional[int] = None
    checkout_percentage: Optional[float] = None
    highest_checkout: Optional[int] = None
    ton_plus_checkouts: Optional[int] = None


@dataclass(frozen=True)
class ModusMatchDetailRecord:
    match_id: int
    player_a_name: str
    player_b_name: str
    player_a_legs: int
    player_b_legs: int
    player_a_stats: ModusPlayerMatchStats
    player_b_stats: ModusPlayerMatchStats
    played_at: Optional[datetime] = None
    series_label: Optional[str] = None
    week_label: Optional[str] = None
    group: Optional[str] = None
