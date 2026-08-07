from __future__ import annotations

import json
from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.player import Player
from app.models.player_career_profile import (
    PlayerCareerProfile,
)
from app.models.player_match_performance import (
    PlayerMatchPerformance,
)
from app.services.statistics_engine_service import (
    StatisticsEngineService,
)


ALL_COMPETITIONS = "ALL"


class PlayerCareerProfileCacheService:
    """Build and refresh materialised player career profiles."""

    def __init__(
        self,
        *,
        statistics_service: Optional[
            StatisticsEngineService
        ] = None,
    ) -> None:
        self.statistics_service = (
            statistics_service or StatisticsEngineService()
        )

    def refresh_player(
        self,
        db: Session,
        *,
        player_id: int,
        competition_code: Optional[str] = None,
        recent_limit: int = 10,
        commit: bool = True,
    ) -> PlayerCareerProfile:
        player = (
            db.query(Player)
            .filter(Player.id == int(player_id))
            .one_or_none()
        )

        if player is None:
            raise ValueError(
                f"Player {player_id} does not exist."
            )

        scope = self._scope(competition_code)
        statistics = (
            self.statistics_service.build_player_statistics(
                db,
                player.id,
                competition_code=competition_code,
                recent_limit=recent_limit,
            )
        )
        first_date, latest_date = self._match_dates(
            db,
            player_id=player.id,
            competition_code=competition_code,
        )

        profile = (
            db.query(PlayerCareerProfile)
            .filter(
                PlayerCareerProfile.player_id == player.id,
                PlayerCareerProfile.competition_code == scope,
            )
            .one_or_none()
        )

        if profile is None:
            profile = PlayerCareerProfile(
                player_id=player.id,
                competition_code=scope,
            )
            db.add(profile)

        profile.matches_played = statistics.matches_played
        profile.wins = statistics.wins
        profile.losses = statistics.losses
        profile.win_percentage = statistics.win_percentage

        profile.legs_won = statistics.legs_won
        profile.legs_lost = statistics.legs_lost
        profile.leg_difference = statistics.leg_difference

        profile.average_three_dart_average = (
            statistics.average_three_dart_average
        )
        profile.average_first_nine_average = (
            statistics.average_first_nine_average
        )

        profile.scores_100_plus = statistics.scores_100_plus
        profile.scores_140_plus = statistics.scores_140_plus
        profile.scores_180 = statistics.scores_180
        profile.maximums_per_match = statistics.maximums_per_match

        profile.checkout_attempts = statistics.checkout_attempts
        profile.checkouts_completed = statistics.checkouts_completed
        profile.calculated_checkout_percentage = (
            statistics.calculated_checkout_percentage
        )
        profile.average_reported_checkout_percentage = (
            statistics.average_reported_checkout_percentage
        )
        profile.highest_checkout = statistics.highest_checkout

        profile.recent_form_json = json.dumps(
            statistics.recent_form
        )
        profile.first_match_date = first_date
        profile.latest_match_date = latest_date
        profile.refreshed_at = datetime.utcnow()

        if commit:
            db.commit()
            db.refresh(profile)
        else:
            db.flush()

        return profile

    def refresh_players(
        self,
        db: Session,
        *,
        player_ids: Iterable[int],
        competition_code: Optional[str] = None,
        recent_limit: int = 10,
    ) -> List[PlayerCareerProfile]:
        unique_ids = sorted(
            {
                int(player_id)
                for player_id in player_ids
            }
        )
        profiles = []

        try:
            for player_id in unique_ids:
                profiles.append(
                    self.refresh_player(
                        db,
                        player_id=player_id,
                        competition_code=competition_code,
                        recent_limit=recent_limit,
                        commit=False,
                    )
                )

            db.commit()

            for profile in profiles:
                db.refresh(profile)

            return profiles

        except Exception:
            db.rollback()
            raise

    def refresh_all(
        self,
        db: Session,
        *,
        competition_code: Optional[str] = None,
        recent_limit: int = 10,
    ) -> List[PlayerCareerProfile]:
        query = (
            db.query(PlayerMatchPerformance.player_id)
            .distinct()
            .order_by(PlayerMatchPerformance.player_id.asc())
        )

        if competition_code:
            query = query.filter(
                PlayerMatchPerformance.competition_code
                == competition_code
            )

        player_ids = [
            row[0]
            for row in query.all()
        ]

        return self.refresh_players(
            db,
            player_ids=player_ids,
            competition_code=competition_code,
            recent_limit=recent_limit,
        )

    @staticmethod
    def recent_form(
        profile: PlayerCareerProfile,
    ) -> List[str]:
        try:
            value = json.loads(
                profile.recent_form_json or "[]"
            )
        except (TypeError, ValueError):
            return []

        return [
            str(item)
            for item in value
            if str(item) in {"W", "L"}
        ]

    @staticmethod
    def _scope(
        competition_code: Optional[str],
    ) -> str:
        return (
            str(competition_code).strip().upper()
            if competition_code
            else ALL_COMPETITIONS
        )

    @staticmethod
    def _match_dates(
        db: Session,
        *,
        player_id: int,
        competition_code: Optional[str],
    ):
        query = (
            db.query(Match.date)
            .join(
                PlayerMatchPerformance,
                PlayerMatchPerformance.match_id == Match.id,
            )
            .filter(
                PlayerMatchPerformance.player_id == player_id,
                Match.date.isnot(None),
            )
        )

        if competition_code:
            query = query.filter(
                PlayerMatchPerformance.competition_code
                == competition_code
            )

        dates = [
            row[0]
            for row in query.order_by(Match.date.asc()).all()
        ]

        if not dates:
            return None, None

        return dates[0], dates[-1]
