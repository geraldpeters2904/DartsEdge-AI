from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.services.live_opportunity_centre_service import (
    build_live_opportunity_centre,
)
from app.services.prediction_centre_service import (
    build_prediction_centre,
)


@dataclass(frozen=True)
class LiveOpportunityPipelineFixture:
    fixture_id: int
    player_a: str
    player_b: str
    tournament: str
    has_opportunity: bool
    has_price: bool
    has_assessment: bool
    has_decision_intelligence: bool
    has_live_opportunity: bool
    state: str
    explanation: str


@dataclass(frozen=True)
class LiveOpportunityPipelineReadiness:
    state: str
    ready: bool
    fixture_count: int
    opportunity_count: int
    priced_count: int
    assessment_count: int
    decision_count: int
    live_opportunity_count: int
    blocked_count: int
    fixtures: Tuple[LiveOpportunityPipelineFixture, ...]
    explanation: str


def _fixture_state(
    *,
    has_opportunity: bool,
    has_price: bool,
    has_assessment: bool,
    has_decision_intelligence: bool,
    has_live_opportunity: bool,
) -> tuple[str, str]:
    if has_live_opportunity:
        return (
            "READY",
            "The fixture reached the Live Opportunity Centre.",
        )

    if not has_opportunity:
        return (
            "WAITING_FOR_PREDICTION",
            "No ranked model opportunity is available for this fixture.",
        )

    if not has_price:
        return (
            "WAITING_FOR_ODDS",
            "A model opportunity exists, but no matching bookmaker price is available.",
        )

    if not has_assessment:
        return (
            "WAITING_FOR_VALUE_ASSESSMENT",
            "A bookmaker price exists, but no value assessment was produced.",
        )

    if not has_decision_intelligence:
        return (
            "WAITING_FOR_DECISION_INTELLIGENCE",
            "The fixture has prediction and value data, but Decision Intelligence is unavailable.",
        )

    return (
        "BLOCKED",
        "The fixture passed the core decision stages but was not emitted as a live opportunity.",
    )


def build_live_opportunity_pipeline_readiness(
    db: Session,
    *,
    limit: int = 30,
) -> LiveOpportunityPipelineReadiness:
    centre = build_prediction_centre(
        db,
        limit=limit,
    )

    live = build_live_opportunity_centre(
        db,
        limit=limit,
        persist=False,
    )

    live_fixture_ids = {
        int(item.fixture_id)
        for item in live.get(
            "opportunities",
            (),
        )
    }

    rows = []

    for card in centre.get(
        "cards",
        (),
    ):
        fixture = card.get(
            "fixture"
        )

        if fixture is None:
            continue

        fixture_id = int(
            fixture.id
        )

        has_opportunity = bool(
            card.get(
                "opportunity"
            )
        )

        has_price = bool(
            card.get(
                "price"
            )
        )

        has_assessment = bool(
            card.get(
                "assessment"
            )
        )

        has_decision_intelligence = bool(
            card.get(
                "decision_intelligence"
            )
        )

        has_live_opportunity = (
            fixture_id
            in live_fixture_ids
        )

        state, explanation = _fixture_state(
            has_opportunity=has_opportunity,
            has_price=has_price,
            has_assessment=has_assessment,
            has_decision_intelligence=(
                has_decision_intelligence
            ),
            has_live_opportunity=(
                has_live_opportunity
            ),
        )

        rows.append(
            LiveOpportunityPipelineFixture(
                fixture_id=fixture_id,
                player_a=str(
                    fixture.player_a
                    or ""
                ),
                player_b=str(
                    fixture.player_b
                    or ""
                ),
                tournament=str(
                    fixture.tournament
                    or "Unknown"
                ),
                has_opportunity=(
                    has_opportunity
                ),
                has_price=has_price,
                has_assessment=(
                    has_assessment
                ),
                has_decision_intelligence=(
                    has_decision_intelligence
                ),
                has_live_opportunity=(
                    has_live_opportunity
                ),
                state=state,
                explanation=explanation,
            )
        )

    fixture_count = len(
        rows
    )

    opportunity_count = sum(
        item.has_opportunity
        for item in rows
    )

    priced_count = sum(
        item.has_price
        for item in rows
    )

    assessment_count = sum(
        item.has_assessment
        for item in rows
    )

    decision_count = sum(
        item.has_decision_intelligence
        for item in rows
    )

    live_opportunity_count = sum(
        item.has_live_opportunity
        for item in rows
    )

    blocked_count = (
        fixture_count
        - live_opportunity_count
    )

    if fixture_count == 0:
        state = "WAITING_FOR_FIXTURES"
        ready = False
        explanation = (
            "No scheduled fixtures are currently available for the live opportunity pipeline."
        )
    elif live_opportunity_count > 0:
        state = "READY"
        ready = True
        explanation = (
            f"{live_opportunity_count} fixture(s) reached the Live Opportunity Centre."
        )
    elif opportunity_count == 0:
        state = "WAITING_FOR_PREDICTIONS"
        ready = False
        explanation = (
            "Scheduled fixtures exist, but no ranked model opportunities are available yet."
        )
    elif priced_count == 0:
        state = "WAITING_FOR_ODDS"
        ready = False
        explanation = (
            "Model opportunities exist, but no matching bookmaker prices are available yet."
        )
    elif assessment_count == 0:
        state = "WAITING_FOR_VALUE_ASSESSMENT"
        ready = False
        explanation = (
            "Bookmaker prices exist, but value assessments have not been produced."
        )
    elif decision_count == 0:
        state = "WAITING_FOR_DECISION_INTELLIGENCE"
        ready = False
        explanation = (
            "Value assessments exist, but Decision Intelligence has not been produced."
        )
    else:
        state = "BLOCKED"
        ready = False
        explanation = (
            "The core stages are present, but no fixture was emitted as a live opportunity."
        )

    return LiveOpportunityPipelineReadiness(
        state=state,
        ready=ready,
        fixture_count=fixture_count,
        opportunity_count=(
            opportunity_count
        ),
        priced_count=priced_count,
        assessment_count=(
            assessment_count
        ),
        decision_count=(
            decision_count
        ),
        live_opportunity_count=(
            live_opportunity_count
        ),
        blocked_count=blocked_count,
        fixtures=tuple(
            rows
        ),
        explanation=explanation,
    )
