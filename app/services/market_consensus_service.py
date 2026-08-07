from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean, pstdev
from typing import Iterable, Optional

from app.models.odds_snapshot import OddsSnapshot
from app.services.closing_line_value_service import canonical_bookmaker


@dataclass(frozen=True)
class BookmakerConsensusPoint:
    bookmaker: str
    latest_odds: float
    implied_probability: float
    distance_from_consensus_points: float
    outlier: bool


@dataclass(frozen=True)
class MarketConsensusReport:
    bookmaker_count: int
    consensus_probability: float
    consensus_odds: float
    dispersion_points: float
    consensus_score: int
    consensus_grade: str
    shortening_count: int
    drifting_count: int
    stable_count: int
    steam_direction: str
    steam_strength: str
    coordinated_move: bool
    outlier_bookmakers: tuple[str, ...]
    bookmaker_points: tuple[BookmakerConsensusPoint, ...]
    positive_reasons: tuple[str, ...]
    caution_reasons: tuple[str, ...]


def _latest_by_bookmaker(rows: Iterable[OddsSnapshot]) -> dict[str, OddsSnapshot]:
    latest = {}
    for row in rows:
        bookmaker = canonical_bookmaker(row.bookmaker)
        current = latest.get(bookmaker)
        if (
            current is None
            or row.captured_at > current.captured_at
            or (
                row.captured_at == current.captured_at
                and (row.id or 0) > (current.id or 0)
            )
        ):
            latest[bookmaker] = row
    return latest


def _opening_by_bookmaker(rows: Iterable[OddsSnapshot]) -> dict[str, OddsSnapshot]:
    opening = {}
    for row in rows:
        bookmaker = canonical_bookmaker(row.bookmaker)
        current = opening.get(bookmaker)
        if (
            current is None
            or row.captured_at < current.captured_at
            or (
                row.captured_at == current.captured_at
                and (row.id or 0) < (current.id or 0)
            )
        ):
            opening[bookmaker] = row
    return opening


def _movement_direction(*, opening_odds: float, latest_odds: float) -> str:
    if opening_odds <= 0:
        return "stable"
    movement_percent = ((latest_odds / opening_odds) - 1.0) * 100.0
    if movement_percent <= -1.0:
        return "shortening"
    if movement_percent >= 1.0:
        return "drifting"
    return "stable"


def _consensus_grade(score: int) -> str:
    if score >= 90:
        return "Very High"
    if score >= 75:
        return "High"
    if score >= 60:
        return "Moderate"
    if score >= 40:
        return "Low"
    return "Very Low"


def _steam_strength(*, bookmaker_count: int, directional_count: int, agreement_ratio: float) -> str:
    if bookmaker_count < 2:
        return "none"
    if directional_count >= 4 and agreement_ratio >= 0.80:
        return "strong"
    if directional_count >= 3 and agreement_ratio >= 0.70:
        return "medium"
    if directional_count >= 2 and agreement_ratio >= 0.60:
        return "light"
    return "none"


def analyse_market_consensus(rows: Iterable[OddsSnapshot]) -> Optional[MarketConsensusReport]:
    rows = list(rows)
    if not rows:
        return None

    latest = _latest_by_bookmaker(rows)
    opening = _opening_by_bookmaker(rows)
    latest_rows = list(latest.values())
    bookmaker_count = len(latest_rows)

    implied_probabilities = [
        100.0 / float(row.decimal_odds)
        for row in latest_rows
        if float(row.decimal_odds) > 1.0
    ]
    if not implied_probabilities:
        return None

    consensus_probability = fmean(implied_probabilities)
    consensus_odds = 100.0 / consensus_probability
    dispersion = pstdev(implied_probabilities) if len(implied_probabilities) > 1 else 0.0

    consensus_score = int(
        round(
            max(
                0.0,
                min(100.0, 100.0 - ((dispersion / 8.0) * 100.0)),
            )
        )
    )

    bookmaker_points = []
    outliers = []

    for bookmaker, row in sorted(latest.items()):
        implied = 100.0 / float(row.decimal_odds)
        distance = abs(implied - consensus_probability)
        outlier = bookmaker_count >= 3 and distance >= 4.0
        if outlier:
            outliers.append(bookmaker)

        bookmaker_points.append(
            BookmakerConsensusPoint(
                bookmaker=bookmaker,
                latest_odds=round(float(row.decimal_odds), 3),
                implied_probability=round(implied, 2),
                distance_from_consensus_points=round(distance, 2),
                outlier=outlier,
            )
        )

    shortening_count = 0
    drifting_count = 0
    stable_count = 0

    for bookmaker, latest_row in latest.items():
        opening_row = opening.get(bookmaker)
        if opening_row is None:
            stable_count += 1
            continue

        direction = _movement_direction(
            opening_odds=float(opening_row.decimal_odds),
            latest_odds=float(latest_row.decimal_odds),
        )

        if direction == "shortening":
            shortening_count += 1
        elif direction == "drifting":
            drifting_count += 1
        else:
            stable_count += 1

    directional_total = max(shortening_count, drifting_count)
    agreement_ratio = directional_total / bookmaker_count if bookmaker_count else 0.0

    if shortening_count > drifting_count and shortening_count >= 2:
        steam_direction = "shortening"
    elif drifting_count > shortening_count and drifting_count >= 2:
        steam_direction = "drifting"
    else:
        steam_direction = "mixed"

    strength = _steam_strength(
        bookmaker_count=bookmaker_count,
        directional_count=directional_total,
        agreement_ratio=agreement_ratio,
    )

    coordinated_move = (
        strength != "none"
        and steam_direction in {"shortening", "drifting"}
    )

    positive = []
    cautions = []

    if consensus_score >= 75:
        positive.append("Bookmakers are showing strong price agreement.")
    elif consensus_score < 50:
        cautions.append("Bookmaker prices are widely dispersed.")

    if coordinated_move:
        if steam_direction == "shortening":
            positive.append(f"{directional_total} bookmakers are shortening together.")
        else:
            cautions.append(f"{directional_total} bookmakers are drifting together.")

    if outliers:
        cautions.append("One or more bookmakers are materially away from consensus.")

    if bookmaker_count < 2:
        cautions.append("Only one bookmaker is available, so consensus is limited.")

    return MarketConsensusReport(
        bookmaker_count=bookmaker_count,
        consensus_probability=round(consensus_probability, 2),
        consensus_odds=round(consensus_odds, 3),
        dispersion_points=round(dispersion, 2),
        consensus_score=consensus_score,
        consensus_grade=_consensus_grade(consensus_score),
        shortening_count=shortening_count,
        drifting_count=drifting_count,
        stable_count=stable_count,
        steam_direction=steam_direction,
        steam_strength=strength,
        coordinated_move=coordinated_move,
        outlier_bookmakers=tuple(outliers),
        bookmaker_points=tuple(bookmaker_points),
        positive_reasons=tuple(positive),
        caution_reasons=tuple(cautions),
    )


def consensus_summary(report: Optional[MarketConsensusReport]) -> Optional[dict]:
    if report is None:
        return None

    return {
        "bookmaker_count": report.bookmaker_count,
        "consensus_probability": report.consensus_probability,
        "consensus_odds": report.consensus_odds,
        "dispersion_points": report.dispersion_points,
        "consensus_score": report.consensus_score,
        "consensus_grade": report.consensus_grade,
        "shortening_count": report.shortening_count,
        "drifting_count": report.drifting_count,
        "stable_count": report.stable_count,
        "steam_direction": report.steam_direction,
        "steam_strength": report.steam_strength,
        "coordinated_move": report.coordinated_move,
        "outlier_bookmakers": list(report.outlier_bookmakers),
        "bookmaker_points": [
            {
                "bookmaker": item.bookmaker,
                "latest_odds": item.latest_odds,
                "implied_probability": item.implied_probability,
                "distance_from_consensus_points": item.distance_from_consensus_points,
                "outlier": item.outlier,
            }
            for item in report.bookmaker_points
        ],
        "positive_reasons": list(report.positive_reasons),
        "caution_reasons": list(report.caution_reasons),
    }
