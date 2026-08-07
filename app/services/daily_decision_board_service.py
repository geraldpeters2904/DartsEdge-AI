from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.services.prediction_centre_service import (
    build_prediction_centre,
)


@dataclass(frozen=True)
class DailyDecision:
    rank: int
    fixture_id: int
    fixture_date: object
    tournament: str
    player_a: str
    player_b: str
    selection: str
    bookmaker: str
    decimal_odds: float

    decision_score: int
    decision_grade: str
    recommendation: str
    stars: int

    model_probability: float
    model_confidence: float
    expected_value_percent: float
    edge_percent: float
    suggested_stake: float

    trust_score: Optional[float]
    evidence_score: Optional[float]
    market_direction: Optional[str]
    market_volatility: Optional[str]
    clv_percent: Optional[float]

    positive_reasons: tuple[str, ...]
    caution_reasons: tuple[str, ...]


def _decision_from_card(
    card: dict[str, Any],
    *,
    rank: int,
) -> DailyDecision:
    fixture = card["fixture"]
    opportunity = card["opportunity"]
    assessment = card["assessment"]
    price = card["price"]
    decision = card["decision_intelligence"]

    return DailyDecision(
        rank=rank,
        fixture_id=int(
            fixture.id
        ),
        fixture_date=(
            fixture.date
        ),
        tournament=str(
            fixture.tournament
            or "Tournament not set"
        ),
        player_a=str(
            fixture.player_a
        ),
        player_b=str(
            fixture.player_b
        ),
        selection=str(
            opportunity[
                "selection"
            ]
        ),
        bookmaker=str(
            price.bookmaker
        ),
        decimal_odds=round(
            float(
                price.decimal_odds
            ),
            3,
        ),
        decision_score=int(
            decision[
                "score"
            ]
        ),
        decision_grade=str(
            decision[
                "grade"
            ]
        ),
        recommendation=str(
            decision[
                "recommendation"
            ]
        ),
        stars=int(
            decision[
                "stars"
            ]
        ),
        model_probability=round(
            float(
                opportunity[
                    "probability"
                ]
            ),
            2,
        ),
        model_confidence=round(
            float(
                opportunity[
                    "model_confidence"
                ]
            ),
            2,
        ),
        expected_value_percent=round(
            float(
                assessment
                .expected_value_percent
            ),
            2,
        ),
        edge_percent=round(
            float(
                assessment
                .edge_percent
            ),
            2,
        ),
        suggested_stake=round(
            float(
                decision.get(
                    "strategy_suggested_stake",
                    assessment
                    .recommended_stake,
                )
                or 0.0
            ),
            2,
        ),
        trust_score=(
            decision.get(
                "trust_score"
            )
        ),
        evidence_score=(
            decision.get(
                "evidence_score"
            )
        ),
        market_direction=(
            decision.get(
                "market_direction"
            )
        ),
        market_volatility=(
            decision.get(
                "market_volatility"
            )
        ),
        clv_percent=(
            decision.get(
                "clv_percent"
            )
        ),
        positive_reasons=tuple(
            decision.get(
                "positive_reasons"
            )
            or ()
        ),
        caution_reasons=tuple(
            decision.get(
                "caution_reasons"
            )
            or ()
        ),
    )


def build_daily_decision_board(
    db,
    *,
    limit: int = 10,
) -> dict[str, Any]:
    safe_limit = max(
        1,
        min(
            int(limit),
            50,
        ),
    )

    centre = (
        build_prediction_centre(
            db,
            limit=max(
                safe_limit,
                30,
            ),
        )
    )

    scored_cards = [
        card
        for card
        in centre["cards"]
        if (
            card.get(
                "decision_intelligence"
            )
            and card.get(
                "opportunity"
            )
            and card.get(
                "assessment"
            )
            and card.get(
                "price"
            )
        )
    ]

    scored_cards.sort(
        key=lambda card: (
            float(
                card[
                    "decision_intelligence"
                ][
                    "score"
                ]
            ),
            float(
                card[
                    "assessment"
                ]
                .expected_value_percent
            ),
            float(
                card[
                    "assessment"
                ]
                .edge_percent
            ),
            float(
                card[
                    "opportunity"
                ][
                    "probability"
                ]
            ),
        ),
        reverse=True,
    )

    decisions = tuple(
        _decision_from_card(
            card,
            rank=index,
        )
        for index, card
        in enumerate(
            scored_cards[
                :safe_limit
            ],
            start=1,
        )
    )

    bet_count = sum(
        item.recommendation
        == "BET"
        for item
        in decisions
    )

    small_bet_count = sum(
        item.recommendation
        == "SMALL BET"
        for item
        in decisions
    )

    watch_count = sum(
        item.recommendation
        == "WATCH"
        for item
        in decisions
    )

    total_stake = round(
        sum(
            item.suggested_stake
            for item
            in decisions
            if item.recommendation
            in {
                "BET",
                "SMALL BET",
            }
        ),
        2,
    )

    average_score = (
        round(
            sum(
                item.decision_score
                for item
                in decisions
            )
            / len(
                decisions
            ),
            1,
        )
        if decisions
        else None
    )

    return {
        "board_date": (
            centre[
                "centre_date"
            ]
        ),
        "fixture_scope": (
            centre[
                "fixture_scope"
            ]
        ),
        "fixture_count": (
            centre[
                "fixture_count"
            ]
        ),
        "decision_scored_count": (
            centre.get(
                "decision_scored_count",
                len(
                    scored_cards
                ),
            )
        ),
        "decisions": decisions,
        "top_decision": (
            decisions[0]
            if decisions
            else None
        ),
        "bet_count": int(
            bet_count
        ),
        "small_bet_count": int(
            small_bet_count
        ),
        "watch_count": int(
            watch_count
        ),
        "total_suggested_stake": (
            total_stake
        ),
        "average_decision_score": (
            average_score
        ),
        "portfolio": (
            centre[
                "portfolio"
            ]
        ),
        "active_strategy": (
            centre[
                "active_strategy"
            ]
        ),
        "decision_engine_active": (
            centre[
                "decision_engine_active"
            ]
        ),
    }
