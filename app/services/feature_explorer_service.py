from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.services.advanced_player_feature_engine import (
    AdvancedPlayerFeatureEngine,
    AdvancedPlayerFeatureProfile,
    AdvancedRollingWindow,
    TrendSignal,
)
from app.services.player_name_service import (
    resolve_player_by_name,
)


@dataclass(frozen=True)
class FeatureExplorerWindow:
    label: str
    matches: int
    wins: int
    losses: int
    win_percentage: Optional[float]
    three_dart_average: Optional[float]
    checkout_percentage: Optional[float]
    scores_180_per_match: Optional[float]
    scores_180_per_leg: Optional[float]
    leg_difference: int
    deciding_win_percentage: Optional[float]
    threw_first_win_percentage: Optional[float]
    threw_second_win_percentage: Optional[float]


@dataclass(frozen=True)
class FeatureExplorerReport:
    player_id: int
    player_name: str
    competition_code: Optional[str]
    matches_available: int
    latest_match_id: Optional[int]
    latest_match_date: Optional[str]

    windows: Tuple[FeatureExplorerWindow, ...]
    trends: Tuple[TrendSignal, ...]

    matches_on_latest_day: int
    legs_on_latest_day: int
    hours_since_previous_match: Optional[float]
    days_since_previous_match: Optional[int]


class FeatureExplorerService:
    """
    Present advanced player features in a compact, inspection-friendly form.

    The service is read-only and is intended for CLI and dashboard diagnostics.
    """

    DISPLAY_WINDOWS = (
        "last_5",
        "last_10",
        "last_20",
        "last_50",
        "career",
    )

    def __init__(
        self,
        *,
        engine: Optional[
            AdvancedPlayerFeatureEngine
        ] = None,
    ) -> None:
        self.engine = (
            engine
            or AdvancedPlayerFeatureEngine()
        )

    def inspect_player(
        self,
        db: Session,
        *,
        player_name: str,
        competition_code: Optional[str] = None,
    ) -> FeatureExplorerReport:
        player = resolve_player_by_name(
            db,
            player_name,
            record_alias=False,
        )

        if player is None:
            raise ValueError(
                f"Player was not found: {player_name}."
            )

        profile = self.engine.build_player_profile(
            db,
            player.id,
            competition_code=competition_code,
        )

        return self._build_report(
            player_id=player.id,
            player_name=player.name,
            profile=profile,
        )

    @classmethod
    def _build_report(
        cls,
        *,
        player_id: int,
        player_name: str,
        profile: AdvancedPlayerFeatureProfile,
    ) -> FeatureExplorerReport:
        windows = tuple(
            cls._window(
                profile.windows[label]
            )
            for label in cls.DISPLAY_WINDOWS
        )

        fatigue = profile.fatigue

        return FeatureExplorerReport(
            player_id=player_id,
            player_name=player_name,
            competition_code=(
                profile.competition_code
            ),
            matches_available=(
                profile.matches_available
            ),
            latest_match_id=(
                profile.latest_match_id
            ),
            latest_match_date=(
                profile.latest_match_date
            ),
            windows=windows,
            trends=profile.trends,
            matches_on_latest_day=(
                fatigue.matches_on_latest_day
            ),
            legs_on_latest_day=(
                fatigue.legs_on_latest_day
            ),
            hours_since_previous_match=(
                fatigue.hours_since_previous_match
            ),
            days_since_previous_match=(
                fatigue.days_since_previous_match
            ),
        )

    @staticmethod
    def _window(
        window: AdvancedRollingWindow,
    ) -> FeatureExplorerWindow:
        return FeatureExplorerWindow(
            label=window.label,
            matches=window.matches,
            wins=window.wins,
            losses=window.losses,
            win_percentage=(
                window.win_percentage
            ),
            three_dart_average=(
                window.average_three_dart_average
            ),
            checkout_percentage=(
                window.checkout_percentage
            ),
            scores_180_per_match=(
                window.scores_180_per_match
            ),
            scores_180_per_leg=(
                window.scores_180_per_leg
            ),
            leg_difference=(
                window.leg_difference
            ),
            deciding_win_percentage=(
                window.deciding_win_percentage
            ),
            threw_first_win_percentage=(
                window.threw_first_win_percentage
            ),
            threw_second_win_percentage=(
                window.threw_second_win_percentage
            ),
        )
