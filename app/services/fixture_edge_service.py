from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.odds_snapshot import OddsSnapshot


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
    """
    Resolve a match-winner probability from the existing prediction stack.

    DartsEdge has evolved through several prediction service generations, so
    this adapter intentionally discovers compatible callables instead of
    hard-coding one historical implementation.
    """
    import importlib
    import inspect

    candidates = (
        (
            "app.services.prediction_centre_service",
            (
                "predict_fixture",
                "prediction_for_fixture",
                "build_fixture_prediction",
            ),
        ),
        (
            "app.services.predictor",
            (
                "predict_match",
                "predict",
            ),
        ),
        (
            "app.services.prediction_service",
            (
                "predict_fixture",
                "predict_match",
                "predict",
            ),
        ),
    )

    for module_name, function_names in candidates:
        try:
            module = importlib.import_module(
                module_name
            )
        except Exception:
            continue

        for function_name in function_names:
            fn = getattr(
                module,
                function_name,
                None,
            )

            if not callable(
                fn
            ):
                continue

            try:
                signature = inspect.signature(
                    fn
                )
            except Exception:
                continue

            kwargs = {}

            names = set(
                signature.parameters
            )

            if "db" in names:
                kwargs["db"] = db
            elif "session" in names:
                kwargs["session"] = db

            if "fixture_id" in names:
                kwargs["fixture_id"] = fixture_id
            elif "match_id" in names:
                kwargs["match_id"] = fixture_id

            if "player_a" in names:
                kwargs["player_a"] = player_a

            if "player_b" in names:
                kwargs["player_b"] = player_b

            try:
                result = fn(
                    **kwargs
                )
            except Exception:
                continue

            probability = _extract_probability(
                result,
                player_a=player_a,
            )

            if probability is not None:
                return probability

    return None


def _extract_probability(
    result,
    *,
    player_a: str,
) -> Optional[float]:
    if result is None:
        return None

    if isinstance(
        result,
        (float, int),
    ):
        value = float(
            result
        )

        if 0.0 < value < 1.0:
            return value

        if 1.0 <= value <= 100.0:
            return value / 100.0

        return None

    if isinstance(
        result,
        dict,
    ):
        for key in (
            "player_a_probability",
            "probability_a",
            "home_probability",
            "win_probability",
            "probability",
            "model_probability",
        ):
            if key not in result:
                continue

            value = result[key]

            try:
                number = float(
                    value
                )
            except Exception:
                continue

            if 0.0 < number < 1.0:
                return number

            if 1.0 <= number <= 100.0:
                return number / 100.0

        winner = result.get(
            "predicted_winner"
        )

        confidence = result.get(
            "confidence"
        )

        if (
            winner
            and confidence is not None
        ):
            try:
                number = float(
                    confidence
                )
            except Exception:
                number = None

            if number is not None:
                if 1.0 <= number <= 100.0:
                    number = (
                        number / 100.0
                    )

                if 0.0 < number < 1.0:
                    return (
                        number
                        if str(winner).strip().casefold()
                        == str(player_a).strip().casefold()
                        else 1.0 - number
                    )

    for attr in (
        "player_a_probability",
        "probability_a",
        "home_probability",
        "win_probability",
        "probability",
        "model_probability",
    ):
        if not hasattr(
            result,
            attr,
        ):
            continue

        try:
            number = float(
                getattr(
                    result,
                    attr,
                )
            )
        except Exception:
            continue

        if 0.0 < number < 1.0:
            return number

        if 1.0 <= number <= 100.0:
            return number / 100.0

    return None


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
