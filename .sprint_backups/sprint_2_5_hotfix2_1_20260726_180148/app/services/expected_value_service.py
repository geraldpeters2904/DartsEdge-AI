from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.odds_snapshot import OddsSnapshot
from app.services.kelly_service import calculate_kelly_stake


@dataclass(frozen=True)
class ValueAssessment:
    model_probability: float
    decimal_odds: float
    implied_probability: float
    edge_percent: float
    expected_value_percent: float
    fair_odds: float
    bookmaker: str
    recommended_stake: float
    kelly_percent: float
    has_value: bool
    decision: str
    risk_level: str


def normalise_probability(value: float) -> float:
    probability = float(value)
    if 0 <= probability <= 1:
        probability *= 100
    if probability <= 0 or probability > 100:
        raise ValueError("Model probability must be greater than 0 and no more than 100.")
    return probability


def assess_value(
    model_probability: float,
    decimal_odds: float,
    bookmaker: str,
    bankroll: float,
    kelly_fraction: float,
    max_daily_risk_percent: float,
    minimum_edge_percent: float = 0.0,
) -> ValueAssessment:
    probability = normalise_probability(model_probability)
    odds = float(decimal_odds)
    if odds <= 1:
        raise ValueError("Decimal odds must be greater than 1.00.")

    implied = 100 / odds
    edge = probability - implied
    ev = ((probability / 100) * odds - 1) * 100
    fair_odds = 100 / probability
    kelly = calculate_kelly_stake(
        probability=probability,
        bookmaker_odds=odds,
        bankroll=bankroll,
        fraction=kelly_fraction,
        max_daily_risk_percent=max_daily_risk_percent,
    )
    has_value = ev > 0 and edge >= float(minimum_edge_percent)

    return ValueAssessment(
        model_probability=round(probability, 2),
        decimal_odds=round(odds, 3),
        implied_probability=round(implied, 2),
        edge_percent=round(edge, 2),
        expected_value_percent=round(ev, 2),
        fair_odds=round(fair_odds, 3),
        bookmaker=bookmaker.strip(),
        recommended_stake=kelly["recommended_stake"] if has_value else 0.0,
        kelly_percent=kelly["kelly_percent"] if has_value else 0.0,
        has_value=has_value,
        decision="Consider" if has_value else "Pass",
        risk_level=kelly["risk_level"] if has_value else "None",
    )


def snapshot_fingerprint(
    fixture_date: date,
    player_a: str,
    player_b: str,
    market: str,
    selection: str,
    bookmaker: str,
    decimal_odds: float,
    captured_at: datetime,
) -> str:
    raw = "|".join([
        fixture_date.isoformat(), player_a.strip().lower(), player_b.strip().lower(),
        market.strip().lower(), selection.strip().lower(), bookmaker.strip().lower(),
        f"{float(decimal_odds):.4f}", captured_at.replace(microsecond=0).isoformat(),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def store_snapshot(
    db: Session,
    *,
    fixture_date: date,
    tournament: str,
    player_a: str,
    player_b: str,
    market: str,
    selection: str,
    bookmaker: str,
    decimal_odds: float,
    captured_at: Optional[datetime] = None,
    provider_id: str = "manual-odds",
    external_id: Optional[str] = None,
) -> tuple[OddsSnapshot, bool]:
    if not player_a.strip() or not player_b.strip() or not selection.strip() or not bookmaker.strip():
        raise ValueError("Players, selection and bookmaker are required.")
    if player_a.strip().lower() == player_b.strip().lower():
        raise ValueError("Fixture players must be different.")
    if float(decimal_odds) <= 1:
        raise ValueError("Decimal odds must be greater than 1.00.")

    captured = captured_at or datetime.utcnow()
    fingerprint = snapshot_fingerprint(
        fixture_date, player_a, player_b, market, selection, bookmaker, decimal_odds, captured
    )
    existing = db.query(OddsSnapshot).filter(OddsSnapshot.fingerprint == fingerprint).first()
    if existing:
        return existing, False

    row = OddsSnapshot(
        fixture_date=fixture_date,
        tournament=tournament.strip() or "Unknown",
        player_a=player_a.strip(),
        player_b=player_b.strip(),
        market=market.strip() or "match_winner",
        selection=selection.strip(),
        bookmaker=bookmaker.strip(),
        decimal_odds=float(decimal_odds),
        captured_at=captured,
        provider_id=provider_id,
        external_id=external_id,
        fingerprint=fingerprint,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, True


def best_prices(rows: Iterable[OddsSnapshot]) -> list[OddsSnapshot]:
    best: dict[tuple, OddsSnapshot] = {}
    for row in rows:
        key = (
            row.fixture_date, row.player_a.lower(), row.player_b.lower(),
            row.market.lower(), row.selection.lower(),
        )
        current = best.get(key)
        if current is None or row.decimal_odds > current.decimal_odds or (
            row.decimal_odds == current.decimal_odds and row.captured_at > current.captured_at
        ):
            best[key] = row
    return sorted(best.values(), key=lambda item: (item.fixture_date, item.player_a, item.selection))


def recent_snapshots(db: Session, limit: int = 100) -> list[OddsSnapshot]:
    return (
        db.query(OddsSnapshot)
        .order_by(OddsSnapshot.captured_at.desc(), OddsSnapshot.id.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
