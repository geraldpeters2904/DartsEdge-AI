from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from app.db import SessionLocal
from app.models.match import Match
from app.models.odds_snapshot import OddsSnapshot
from app.services.live_opportunity_pipeline_readiness_service import (
    build_live_opportunity_pipeline_readiness,
)
from app.services.opportunity_ranking_service import (
    build_ranked_opportunities,
)


TEMP_TOURNAMENT = "DARTSEDGE E2E REHEARSAL"
TEMP_SOURCE = "dartsedge-e2e-rehearsal"
TEMP_BOOKMAKER = "Paddy Power"


def _normalise(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().split())


def _player_history_counts(db):
    rows = (
        db.query(Match)
        .filter(Match.status == "completed")
        .all()
    )

    counts = Counter()
    display_names = {}

    for row in rows:
        for raw_name in (row.player_a, row.player_b):
            name = str(raw_name or "").strip()
            key = _normalise(name)

            if not key:
                continue

            counts[key] += 1
            display_names.setdefault(key, name)

    return [
        (display_names[key], count)
        for key, count in counts.most_common()
    ]


def _choose_players(db):
    eligible = [
        (name, count)
        for name, count in _player_history_counts(db)
        if count >= 10 and "demo" not in name.casefold()
    ]

    if len(eligible) < 2:
        raise RuntimeError(
            "Could not find two established players "
            "with sufficient completed-match history."
        )

    player_a, history_a = eligible[0]

    for name, count in eligible[1:]:
        if _normalise(name) != _normalise(player_a):
            return player_a, name, history_a, count

    raise RuntimeError(
        "Could not find two distinct established players."
    )


def _find_fixture_opportunity(
    db,
    *,
    fixture_id: int,
    player_a: str,
    player_b: str,
):
    ranked = build_ranked_opportunities(db, limit=100)

    target_key = {
        _normalise(player_a),
        _normalise(player_b),
    }

    for item in ranked:
        match_id = item.get("match_id")

        if match_id is not None and int(match_id) == int(fixture_id):
            return item

        item_key = {
            _normalise(item.get("player_a")),
            _normalise(item.get("player_b")),
        }

        if item_key == target_key:
            return item

    return None


def _safe_decimal_odds(opportunity):
    fair_odds = float(opportunity.get("fair_odds") or 0.0)
    minimum_odds = float(opportunity.get("minimum_odds") or 0.0)

    candidate = max(
        minimum_odds + 0.10,
        fair_odds * 1.20,
        1.50,
    )

    return round(candidate, 2)


def _print_readiness(result):
    print()
    print("LIVE OPPORTUNITY PIPELINE READINESS")
    print("=" * 74)
    print("State:                ", result.state)
    print("Ready:                ", result.ready)
    print("Scheduled fixtures:   ", result.fixture_count)
    print("With opportunity:     ", result.opportunity_count)
    print("With bookmaker price: ", result.priced_count)
    print("With assessment:      ", result.assessment_count)
    print("With decision intel:  ", result.decision_count)
    print("Live opportunities:   ", result.live_opportunity_count)
    print("Blocked:              ", result.blocked_count)
    print()
    print(result.explanation)

    for item in result.fixtures:
        print()
        print(
            f"{item.fixture_id}: "
            f"{item.player_a} v {item.player_b}"
        )
        print("  State:       ", item.state)
        print("  Opportunity: ", item.has_opportunity)
        print("  Price:       ", item.has_price)
        print("  Assessment:  ", item.has_assessment)
        print("  Decision:    ", item.has_decision_intelligence)
        print("  Live:        ", item.has_live_opportunity)
        print("  Explanation: ", item.explanation)


def main():
    db = SessionLocal()
    fixture = None
    odds_id = None

    try:
        (
            player_a,
            player_b,
            history_a,
            history_b,
        ) = _choose_players(db)

        fixture_date = date.today() + timedelta(days=1)

        print()
        print("DARTSEDGE CONTROLLED E2E REHEARSAL")
        print("=" * 74)
        print("Temporary fixture date:", fixture_date)
        print(
            "Player A:",
            player_a,
            f"({history_a} completed matches)",
        )
        print(
            "Player B:",
            player_b,
            f"({history_b} completed matches)",
        )

        fixture = Match(
            date=fixture_date,
            tournament=TEMP_TOURNAMENT,
            stage="Rehearsal",
            match_format="Best of 7",
            status="scheduled",
            player_a=player_a,
            player_b=player_b,
        )

        db.add(fixture)
        db.commit()
        db.refresh(fixture)

        print("Temporary fixture id:", fixture.id)

        opportunity = _find_fixture_opportunity(
            db,
            fixture_id=fixture.id,
            player_a=player_a,
            player_b=player_b,
        )

        if opportunity is None:
            readiness = build_live_opportunity_pipeline_readiness(db)
            _print_readiness(readiness)
            raise RuntimeError(
                "The temporary fixture did not produce "
                "a ranked model opportunity."
            )

        selection = str(
            opportunity.get("selection") or ""
        ).strip()

        if not selection:
            raise RuntimeError(
                "The ranked opportunity did not contain a selection."
            )

        probability = float(opportunity.get("probability") or 0.0)
        fair_odds = float(opportunity.get("fair_odds") or 0.0)
        decimal_odds = _safe_decimal_odds(opportunity)

        print()
        print("MODEL OPPORTUNITY")
        print("-" * 74)
        print("Selection:         ", selection)
        print("Probability:       ", probability)
        print("Fair odds:         ", fair_odds)
        print("Temporary PP odds: ", decimal_odds)

        odds = OddsSnapshot(
            fixture_id=fixture.id,
            bookmaker_code="paddypower",
            market="match_winner",
            selection=selection,
            decimal_odds=decimal_odds,
            implied_probability=(100.0 / decimal_odds),
            captured_at=datetime.utcnow(),
            source_reference=TEMP_SOURCE,
            fixture_date=fixture_date,
            tournament=TEMP_TOURNAMENT,
            player_a=player_a,
            player_b=player_b,
            bookmaker=TEMP_BOOKMAKER,
            provider_id=TEMP_SOURCE,
            external_id=f"{TEMP_SOURCE}-{fixture.id}",
            fingerprint=(
                f"{TEMP_SOURCE}-{fixture.id}-"
                f"{_normalise(selection)}"
            ),
        )

        db.add(odds)
        db.commit()
        db.refresh(odds)
        odds_id = odds.id

        print("Temporary odds id:", odds.id)

        readiness = build_live_opportunity_pipeline_readiness(db)
        _print_readiness(readiness)

        matching = [
            item
            for item in readiness.fixtures
            if item.fixture_id == fixture.id
        ]

        if not matching:
            raise RuntimeError(
                "The rehearsal fixture was not present "
                "in pipeline readiness."
            )

        item = matching[0]

        print()
        print("REHEARSAL RESULT")
        print("=" * 74)

        if item.has_live_opportunity:
            print(
                "PASS — the temporary fixture reached "
                "the Live Opportunity Centre."
            )
        else:
            print(
                "PARTIAL — the temporary fixture stopped "
                f"at {item.state}."
            )
            print(item.explanation)

    finally:
        try:
            if odds_id is not None:
                persistent_odds = db.get(OddsSnapshot, odds_id)
                if persistent_odds is not None:
                    db.delete(persistent_odds)

            if fixture is not None:
                persistent_fixture = db.get(Match, fixture.id)
                if persistent_fixture is not None:
                    db.delete(persistent_fixture)

            db.commit()

            print()
            print("CLEANUP")
            print("=" * 74)
            print(
                "Temporary rehearsal fixture and odds "
                "were removed."
            )

        except Exception:
            db.rollback()
            print()
            print(
                "WARNING: automatic cleanup failed. "
                "Check TEMP tournament/source markers."
            )
            raise

        finally:
            db.close()


if __name__ == "__main__":
    main()
