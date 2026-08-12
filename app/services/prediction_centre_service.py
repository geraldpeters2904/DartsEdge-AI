from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.models.market_snapshot_analysis import MarketSnapshotAnalysis
from app.models.match import Match
from app.models.odds_snapshot import OddsSnapshot
from app.services.daily_briefing_service import _value_opportunities
from app.services.decision_intelligence_service import (
    build_decision_intelligence,
    decision_intelligence_summary,
)
from app.services.market_consensus_service import (
    analyse_market_consensus,
    consensus_summary,
)
from app.services.model_trust_monitor_service import (
    model_trust_monitor,
)
from app.services.opportunity_ranking_service import build_ranked_opportunities
from app.services.portfolio_health_service import build_portfolio_health
from app.services.prediction_evidence_service import (
    build_prediction_evidence,
    evidence_summary,
)
from app.services.prediction_stability_service import (
    analyse_snapshot_stability,
    stability_summary,
)
from app.services.settings_service import get_settings
from app.services.strategy_service import (
    evaluate_strategy,
    get_active_strategy,
    strategy_rules,
    strategy_summary,
)


def _normalise(value: str | None) -> str:
    return " ".join(
        (value or "").strip().lower().split()
    )


def _fixture_key(player_a: str, player_b: str) -> frozenset[str]:
    return frozenset((
        _normalise(player_a),
        _normalise(player_b),
    ))


def _scheduled_fixtures(db, *, limit: int):
    today = date.today()
    safe_limit = max(1, min(limit, 100))

    fixtures = (
        db.query(Match)
        .filter(
            Match.date == today,
            Match.status == "scheduled",
        )
        .order_by(
            Match.date.asc(),
            Match.id.asc(),
        )
        .limit(safe_limit)
        .all()
    )

    if fixtures:
        return fixtures, "today", today, today

    end_date = today + timedelta(days=7)

    fixtures = (
        db.query(Match)
        .filter(
            Match.date > today,
            Match.date <= end_date,
            Match.status == "scheduled",
        )
        .order_by(
            Match.date.asc(),
            Match.id.asc(),
        )
        .limit(safe_limit)
        .all()
    )

    return fixtures, "upcoming", today + timedelta(days=1), end_date


def _cached_trust_report(db):
    """
    Return the latest background-refreshed trust report.

    Heavy historical validation is performed by
    model_trust_monitor rather than an interactive request.
    """
    return model_trust_monitor.latest_report()


def _card_intelligence(
    *,
    opportunity: Optional[dict],
    assessment,
    trust_report,
) -> tuple[Optional[dict], Optional[dict]]:
    if not opportunity:
        return None, None

    context = opportunity.get("_prediction_context")
    stability_report = None

    if context is not None:
        try:
            stability_report = analyse_snapshot_stability(
                context.snapshot
            )
        except Exception:
            stability_report = None

    try:
        evidence = build_prediction_evidence(
            opportunity=opportunity,
            trust_report=trust_report,
            stability_report=stability_report,
            assessment=assessment,
        )
    except Exception:
        evidence = None

    return (
        stability_summary(stability_report)
        if stability_report is not None
        else None,
        evidence_summary(evidence)
        if evidence is not None
        else None,
    )


def _matched_market_analysis(
    db,
    *,
    fixture,
    opportunity: Optional[dict],
    price,
):
    if not opportunity or not price:
        return None

    selection = str(
        opportunity.get("selection", "")
    ).strip()

    if not selection:
        return None

    query = (
        db.query(MarketSnapshotAnalysis)
        .filter(
            MarketSnapshotAnalysis.fixture_date == fixture.date,
            MarketSnapshotAnalysis.market == "match_winner",
            MarketSnapshotAnalysis.selection == selection,
        )
    )

    bookmaker = str(
        getattr(price, "bookmaker", "") or ""
    ).strip()

    if bookmaker:
        exact = (
            query.filter(
                MarketSnapshotAnalysis.bookmaker == bookmaker
            )
            .order_by(
                MarketSnapshotAnalysis.analysed_at.desc()
            )
            .first()
        )

        if exact is not None:
            return exact

    return (
        query.order_by(
            MarketSnapshotAnalysis.analysed_at.desc()
        )
        .first()
    )


def _matched_consensus(
    db,
    *,
    fixture,
    opportunity: Optional[dict],
) -> Optional[dict]:
    if not opportunity:
        return None

    selection = str(
        opportunity.get("selection", "")
    ).strip()

    if not selection:
        return None

    rows = (
        db.query(OddsSnapshot)
        .filter(
            OddsSnapshot.fixture_date == fixture.date,
            OddsSnapshot.market == "match_winner",
        )
        .order_by(
            OddsSnapshot.captured_at.asc(),
            OddsSnapshot.id.asc(),
        )
        .all()
    )

    matching = [
        row
        for row in rows
        if (
            _fixture_key(
                row.player_a,
                row.player_b,
            )
            == _fixture_key(
                fixture.player_a,
                fixture.player_b,
            )
            and _normalise(row.selection)
            == _normalise(selection)
        )
    ]

    if not matching:
        return None

    try:
        return consensus_summary(
            analyse_market_consensus(
                matching
            )
        )
    except Exception:
        return None


def _decision_intelligence_for_card(
    *,
    opportunity: Optional[dict],
    assessment,
    evidence: Optional[dict],
    trust_report,
    market_analysis,
    market_consensus: Optional[dict] = None,
    portfolio: dict,
    active_strategy_record,
    settings,
) -> Optional[dict]:
    if not opportunity or assessment is None:
        return None

    probability = float(
        opportunity.get("probability", 0.0) or 0.0
    )

    confidence = float(
        opportunity.get(
            "model_confidence",
            probability,
        )
        or probability
    )

    history = min(
        int(
            opportunity.get(
                "player_a_history_matches",
                0,
            )
            or 0
        ),
        int(
            opportunity.get(
                "player_b_history_matches",
                0,
            )
            or 0
        ),
    )

    exposure = (
        portfolio.get("exposure_percent")
        if portfolio
        else None
    )

    bankroll = float(
        getattr(settings, "bankroll", 0.0) or 0.0
    )

    rules = strategy_rules(
        active_strategy_record
    )

    strategy_decision = evaluate_strategy(
        active_strategy_record,
        model_probability=assessment.model_probability,
        confidence_percent=confidence,
        expected_value_percent=assessment.expected_value_percent,
        edge_percent=assessment.edge_percent,
        decimal_odds=assessment.decimal_odds,
        bankroll=bankroll,
        raw_kelly_stake=assessment.recommended_stake,
        market="match_winner",
        competition=str(
            opportunity.get("tournament", "") or ""
        ),
        sample_size=history,
        portfolio_exposure_percent=exposure,
    )

    report = build_decision_intelligence(
        model_probability=probability,
        model_confidence=confidence,
        expected_value_percent=assessment.expected_value_percent,
        edge_percent=assessment.edge_percent,
        suggested_stake=strategy_decision.suggested_stake,
        bankroll=bankroll,
        evidence_score=(
            evidence.get("evidence_score")
            if evidence
            else None
        ),
        trust_score=(
            trust_report.trust_score
            if trust_report is not None
            else None
        ),
        portfolio_exposure_percent=exposure,
        maximum_portfolio_exposure_percent=(
            rules["maximum_portfolio_exposure_percent"]
        ),
        market_direction=(
            market_analysis.movement_direction
            if market_analysis is not None
            else None
        ),
        market_volatility=(
            market_analysis.volatility
            if market_analysis is not None
            else None
        ),
        clv_percent=(
            market_analysis.clv_percent
            if market_analysis is not None
            else None
        ),
        consensus_score=(
            market_consensus.get("consensus_score")
            if market_consensus
            else None
        ),
        steam_direction=(
            market_consensus.get("steam_direction")
            if market_consensus
            else None
        ),
        steam_strength=(
            market_consensus.get("steam_strength")
            if market_consensus
            else None
        ),
        coordinated_move=bool(
            market_consensus.get("coordinated_move")
            if market_consensus
            else False
        ),
        strategy_qualifies=strategy_decision.qualifies,
        strategy_blockers=strategy_decision.blockers,
    )

    payload = decision_intelligence_summary(
        report
    )

    payload["strategy_status"] = (
        strategy_decision.status
    )

    payload["strategy_suggested_stake"] = (
        strategy_decision.suggested_stake
    )

    return payload


def build_prediction_centre(
    db,
    *,
    limit: int = 30,
) -> Dict[str, Any]:
    today = date.today()

    (
        fixtures,
        fixture_scope,
        range_start,
        range_end,
    ) = _scheduled_fixtures(
        db,
        limit=limit,
    )

    ranked = build_ranked_opportunities(
        db,
        limit=max(limit, 100),
    )

    ranked_by_match = {
        item.get("match_id"): item
        for item in ranked
        if item.get("match_id")
    }

    ranked_by_players = {
        _fixture_key(
            item.get("player_a", ""),
            item.get("player_b", ""),
        ): item
        for item in ranked
    }

    values = _value_opportunities(
        db,
        limit=100,
    )

    value_by_match = {
        item.get("match_id"): item
        for item in values
        if item.get("match_id")
    }

    value_by_players = {
        _fixture_key(
            item.get("player_a", ""),
            item.get("player_b", ""),
        ): item
        for item in values
    }

    trust_report = _cached_trust_report(db)
    portfolio = build_portfolio_health(db)
    settings = get_settings(db)

    active_strategy_record = get_active_strategy(db)

    active_strategy = strategy_summary(
        active_strategy_record
    )

    cards: List[Dict[str, Any]] = []

    for fixture in fixtures:
        key = _fixture_key(
            fixture.player_a,
            fixture.player_b,
        )

        opportunity = (
            ranked_by_match.get(fixture.id)
            or ranked_by_players.get(key)
        )

        value = (
            value_by_match.get(fixture.id)
            or value_by_players.get(key)
        )

        assessment = (
            value.get("assessment")
            if value
            else None
        )

        price = (
            value.get("price")
            if value
            else None
        )

        if assessment and assessment.has_value:
            tone = "good"
            status = "Positive EV"
        elif opportunity:
            tone = "warning"
            status = (
                "Odds required"
                if not price
                else "No value"
            )
        else:
            tone = "neutral"
            status = "Analysis unavailable"

        stability, evidence = _card_intelligence(
            opportunity=opportunity,
            assessment=assessment,
            trust_report=trust_report,
        )

        market_analysis = _matched_market_analysis(
            db,
            fixture=fixture,
            opportunity=opportunity,
            price=price,
        )

        market_consensus = _matched_consensus(
            db,
            fixture=fixture,
            opportunity=opportunity,
        )

        decision_intelligence = _decision_intelligence_for_card(
            opportunity=opportunity,
            assessment=assessment,
            evidence=evidence,
            trust_report=trust_report,
            market_analysis=market_analysis,
            market_consensus=market_consensus,
            portfolio=portfolio,
            active_strategy_record=active_strategy_record,
            settings=settings,
        )

        cards.append({
            "fixture": fixture,
            "opportunity": opportunity,
            "value": value,
            "assessment": assessment,
            "price": price,
            "status": status,
            "tone": tone,
            "model_trust": (
                {
                    "trust_score": trust_report.trust_score,
                    "trust_grade": trust_report.trust_grade,
                    "sample_size": trust_report.sample_size,
                }
                if trust_report is not None
                else None
            ),
            "stability": stability,
            "evidence": evidence,
            "market_analysis": market_analysis,
            "market_consensus": market_consensus,
            "decision_intelligence": decision_intelligence,
        })

    coach = {
        "summary": (
            "Open the full AI Coach for portfolio, "
            "opportunity and strategy guidance."
        ),
    }

    confirmed = [
        card
        for card in cards
        if (
            card["assessment"]
            and card["assessment"].has_value
        )
    ]

    competitions = sorted({
        card["fixture"].tournament
        or "Tournament not set"
        for card in cards
    })

    for card in cards:
        opportunity = card["opportunity"] or {}
        assessment = card["assessment"]

        probability = opportunity.get(
            "probability",
            0,
        )

        try:
            probability = float(probability)
        except (TypeError, ValueError):
            probability = 0.0

        card["sort_probability"] = probability

        card["sort_ev"] = (
            float(assessment.expected_value_percent)
            if assessment
            else -999.0
        )

        card["sort_edge"] = (
            float(assessment.edge_percent)
            if assessment
            else -999.0
        )

        card["sort_stake"] = (
            float(assessment.recommended_stake)
            if assessment
            else 0.0
        )

        card["sort_decision"] = (
            float(
                card["decision_intelligence"]["score"]
            )
            if card["decision_intelligence"]
            else -999.0
        )

        card["competition"] = (
            card["fixture"].tournament
            or "Tournament not set"
        )

    decision_cards = [
        card
        for card in cards
        if card["decision_intelligence"]
    ]

    decision_cards.sort(
        key=lambda card: (
            card["sort_decision"],
            card["sort_ev"],
            card["sort_probability"],
        ),
        reverse=True,
    )

    top_card = (
        decision_cards[0]
        if decision_cards
        else (
            confirmed[0]
            if confirmed
            else (
                cards[0]
                if cards
                else None
            )
        )
    )

    return {
        "centre_date": today,
        "cards": cards,
        "fixture_count": len(cards),
        "fixture_scope": fixture_scope,
        "fixture_range_start": range_start,
        "fixture_range_end": range_end,
        "fixture_metric_label": (
            "Today’s fixtures"
            if fixture_scope == "today"
            else "Upcoming fixtures"
        ),
        "fixture_metric_note": (
            "Scheduled today"
            if fixture_scope == "today"
            else "Next seven days"
        ),
        "confirmed_value_count": len(confirmed),
        "decision_scored_count": len(decision_cards),
        "competitions": competitions,
        "top_card": top_card,
        "portfolio": portfolio,
        "coach": coach,
        "active_strategy": active_strategy,
        "decision_engine_active": (
            active_strategy["decision_rules_enabled"]
            and active_strategy["enforcement_mode"]
            == "active"
        ),
        "model_trust": (
            {
                "trust_score": trust_report.trust_score,
                "trust_grade": trust_report.trust_grade,
                "sample_size": trust_report.sample_size,
            }
            if trust_report is not None
            else None
        ),
    }
