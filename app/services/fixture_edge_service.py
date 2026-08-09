from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.odds_snapshot import OddsSnapshot
from app.services.fixture_prediction_adapter_service import predict_fixture


@dataclass(frozen=True)
class FixtureEdgeRow:
    fixture_id: int
    fixture_date: date
    tournament: str
    player_a: str
    player_b: str
    selection: str
    model_probability: Optional[float]
    fair_odds: Optional[float]
    bookmaker_code: Optional[str]
    bookmaker_odds: Optional[float]
    implied_probability: Optional[float]
    edge_percent: Optional[float]
    expected_value_percent: Optional[float]
    classification: str
    message: str


def probability_to_fair_odds(
    probability: float,
) -> float:
    p = float(probability)

    if p <= 0.0 or p >= 1.0:
        raise ValueError(
            "Probability must be between 0 and 1."
        )

    return round(
        1.0 / p,
        4,
    )


def decimal_odds_to_implied_probability(
    decimal_odds: float,
) -> float:
    odds = float(decimal_odds)

    if odds <= 1.0:
        raise ValueError(
            "Decimal odds must be greater than 1.0."
        )

    return round(
        1.0 / odds,
        6,
    )


def classify_edge(
    edge_percent: Optional[float],
) -> str:
    if edge_percent is None:
        return "NO MARKET"

    value = float(
        edge_percent
    )

    if value >= 5.0:
        return "STRONG VALUE"

    if value >= 2.0:
        return "VALUE"

    if value > 0.0:
        return "WATCH"

    return "NO BET"


def expected_value_percent(
    *,
    model_probability: float,
    decimal_odds: float,
) -> float:
    p = float(
        model_probability
    )

    odds = float(
        decimal_odds
    )

    return round(
        (
            p * odds
            - 1.0
        )
        * 100.0,
        2,
    )


def _latest_price(
    db: Session,
    *,
    fixture_id: int,
    selection: str,
    market: str = "match_winner",
) -> Optional[OddsSnapshot]:
    return (
        db.query(OddsSnapshot)
        .filter(
            OddsSnapshot.fixture_id
            == int(
                fixture_id
            ),
            OddsSnapshot.market
            == market,
            OddsSnapshot.selection
            == selection,
        )
        .order_by(
            OddsSnapshot.captured_at.desc(),
            OddsSnapshot.id.desc(),
        )
        .first()
    )


def _prediction_probability(
    db: Session,
    *,
    fixture_id: int,
    player_a: str,
    player_b: str,
) -> Optional[float]:
    result = predict_fixture(
        db,
        fixture_id=fixture_id,
    )

    if not result.ready:
        return None

    return result.player_a_probability



def build_fixture_edge_rows(
    db: Session,
    *,
    today: Optional[date] = None,
    limit: int = 100,
) -> tuple[FixtureEdgeRow, ...]:
    current_day = (
        today
        or date.today()
    )

    fixtures = (
        db.query(Match)
        .filter(
            Match.status
            == "scheduled",
            Match.date
            >= current_day,
        )
        .order_by(
            Match.date.asc(),
            Match.id.asc(),
        )
        .limit(
            max(
                1,
                int(limit),
            )
        )
        .all()
    )

    output = []

    for fixture in fixtures:
        tournament = (
            fixture.tournament
            or ""
        )

        if (
            "modus"
            not in tournament.casefold()
        ):
            continue

        player_a_probability = (
            _prediction_probability(
                db,
                fixture_id=fixture.id,
                player_a=fixture.player_a,
                player_b=fixture.player_b,
            )
        )

        if player_a_probability is None:
            player_probabilities = (
                (
                    fixture.player_a,
                    None,
                ),
                (
                    fixture.player_b,
                    None,
                ),
            )
        else:
            player_probabilities = (
                (
                    fixture.player_a,
                    player_a_probability,
                ),
                (
                    fixture.player_b,
                    1.0
                    - player_a_probability,
                ),
            )

        for selection, probability in player_probabilities:
            price = _latest_price(
                db,
                fixture_id=fixture.id,
                selection=selection,
            )

            bookmaker_odds = (
                float(
                    price.decimal_odds
                )
                if price is not None
                else None
            )

            bookmaker_code = (
                price.bookmaker_code
                if price is not None
                else None
            )

            implied = (
                decimal_odds_to_implied_probability(
                    bookmaker_odds
                )
                if bookmaker_odds is not None
                else None
            )

            fair = (
                probability_to_fair_odds(
                    probability
                )
                if probability is not None
                else None
            )

            edge = (
                round(
                    (
                        probability
                        - implied
                    )
                    * 100.0,
                    2,
                )
                if (
                    probability is not None
                    and implied is not None
                )
                else None
            )

            ev = (
                expected_value_percent(
                    model_probability=probability,
                    decimal_odds=bookmaker_odds,
                )
                if (
                    probability is not None
                    and bookmaker_odds is not None
                )
                else None
            )

            if probability is None:
                message = (
                    "No compatible prediction probability is available yet."
                )
            elif bookmaker_odds is None:
                message = (
                    "Prediction ready; awaiting bookmaker odds."
                )
            else:
                message = (
                    "Prediction and market price are both available."
                )

            output.append(
                FixtureEdgeRow(
                    fixture_id=int(
                        fixture.id
                    ),
                    fixture_date=fixture.date,
                    tournament=tournament,
                    player_a=fixture.player_a,
                    player_b=fixture.player_b,
                    selection=selection,
                    model_probability=probability,
                    fair_odds=fair,
                    bookmaker_code=bookmaker_code,
                    bookmaker_odds=bookmaker_odds,
                    implied_probability=implied,
                    edge_percent=edge,
                    expected_value_percent=ev,
                    classification=(
                        classify_edge(
                            edge
                        )
                    ),
                    message=message,
                )
            )

    return tuple(
        output
    )
