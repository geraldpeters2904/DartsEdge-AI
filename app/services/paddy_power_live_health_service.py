from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.services.paddy_power_live_capture import (
    build_paddy_power_capture_once,
)
from app.services.paddy_power_live_bridge import (
    PaddyPowerBridgeResolution,
)
from app.models.match import Match
from app.models.odds_snapshot import OddsSnapshot
from app.models.player import Player
from app.models.player_career_profile import PlayerCareerProfile
from app.services.player_career_profile_cache_service import (
    ALL_COMPETITIONS,
)


@dataclass(frozen=True)
class PaddyPowerLiveHealth:
    ready: bool
    module_name: Optional[str]
    function_name: Optional[str]
    message: str
    error: Optional[str] = None


def resolve_capture_callable(
) -> PaddyPowerBridgeResolution:
    """
    Local compatibility wrapper.

    Older tests patch this name directly.
    Newer tests patch build_paddy_power_capture_once directly.
    Both therefore exercise the same health-check path.
    """
    capture_once, service = (
        build_paddy_power_capture_once()
    )

    try:
        if not callable(
            capture_once
        ):
            raise TypeError(
                "build_paddy_power_capture_once() did not return "
                "a callable capture function."
            )

        return PaddyPowerBridgeResolution(
            module_name=(
                "app.services.paddy_power_live_capture"
            ),
            function_name=(
                "build_paddy_power_capture_once"
            ),
            callable=capture_once,
        )

    finally:
        service.close()


def check_paddy_power_live_health(
) -> PaddyPowerLiveHealth:
    try:
        resolution = (
            resolve_capture_callable()
        )

        return PaddyPowerLiveHealth(
            ready=True,
            module_name=(
                resolution.module_name
            ),
            function_name=(
                resolution.function_name
            ),
            message=(
                "Paddy Power live bridge is ready."
            ),
        )

    except Exception as exc:
        return PaddyPowerLiveHealth(
            ready=False,
            module_name=None,
            function_name=None,
            message=(
                "Paddy Power live bridge is not ready."
            ),
            error=str(
                exc
            ),
        )


def build_paddy_power_fixture_diagnostics(
    db,
    *,
    today=None,
):
    today = today or date.today()

    fixtures = (
        db.query(Match)
        .filter(
            Match.status == "scheduled",
            Match.date >= today,
        )
        .order_by(
            Match.date.asc(),
            Match.id.asc(),
        )
        .all()
    )

    diagnostics = []

    for fixture in fixtures:
        snapshots = (
            db.query(OddsSnapshot)
            .filter(
                OddsSnapshot.fixture_id == fixture.id,
                OddsSnapshot.bookmaker_code == "paddypower",
            )
            .all()
        )

        markets = sorted({
            row.market
            for row in snapshots
            if getattr(row, "market", None)
        })

        captured_times = [
            row.captured_at
            for row in snapshots
            if getattr(row, "captured_at", None) is not None
        ]

        def latest_match_date_for(player_name):
            player = (
                db.query(Player)
                .filter(
                    Player.name == player_name
                )
                .one_or_none()
            )

            if player is None:
                return None

            profile = (
                db.query(PlayerCareerProfile)
                .filter(
                    PlayerCareerProfile.player_id
                    == player.id,
                    PlayerCareerProfile.competition_code
                    == ALL_COMPETITIONS,
                )
                .one_or_none()
            )

            if profile is None:
                return None

            return profile.latest_match_date

        def is_stale(latest_match_date):
            if (
                latest_match_date is None
                or fixture.date is None
            ):
                return False

            return (
                fixture.date - latest_match_date
            ).days > 180

        player_a_latest_match_date = (
            latest_match_date_for(
                fixture.player_a
            )
        )

        player_b_latest_match_date = (
            latest_match_date_for(
                fixture.player_b
            )
        )

        player_a_stale = is_stale(
            player_a_latest_match_date
        )

        player_b_stale = is_stale(
            player_b_latest_match_date
        )

        diagnostics.append({
            "fixture_id": fixture.id,
            "fixture_date": fixture.date,
            "player_a": fixture.player_a,
            "player_b": fixture.player_b,
            "markets": markets,
            "latest_capture_at": (
                max(captured_times)
                if captured_times
                else None
            ),
            "player_a_stale": player_a_stale,
            "player_b_stale": player_b_stale,
            "leg_markets_eligible": not (
                player_a_stale
                or player_b_stale
            ),
        })

    return diagnostics
