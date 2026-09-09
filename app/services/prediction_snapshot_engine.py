from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence, Tuple

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.player import Player
from app.models.player_match_performance import (
    PlayerMatchPerformance,
)
from app.services.player_feature_engine import (
    PlayerFeatureEngine,
    PlayerFeatureProfile,
)
from app.services.player_name_service import (
    resolve_player_by_name,
)
from app.services.player_rating_engine import (
    PlayerRatingEngine,
)


@dataclass(frozen=True)
class PlayerPredictionSnapshot:
    player_id: int
    player_name: str

    overall_rating: float
    scoring_rating: float
    finishing_rating: float
    maximums_rating: float
    form_rating: float

    momentum_score: Optional[float]
    confidence_score: float
    matches_available: int
    latest_match_date: Optional[str]

    last_5_wins: int
    last_5_matches: int
    last_10_wins: int
    last_10_matches: int
    last_20_wins: int
    last_20_matches: int

    last_10_average: Optional[float]
    last_10_180s_per_match: Optional[float]
    last_10_checkout_percentage: Optional[float]
    last_10_leg_difference: int


@dataclass(frozen=True)
class MatchPredictionSnapshot:
    match_id: int
    match_date: Optional[str]
    tournament: Optional[str]
    stage: Optional[str]

    player_a: PlayerPredictionSnapshot
    player_b: PlayerPredictionSnapshot

    overall_edge: float
    scoring_edge: float
    finishing_edge: float
    maximums_edge: float
    form_edge: float
    momentum_edge: Optional[float]
    confidence_edge: float


class PredictionSnapshotEngine:
    """
    Build pre-match snapshots for historical back-testing.

    Only performances known before the target match are included. When both
    the target and historical performances expose observed_at, that timestamp
    is the primary cutoff. Otherwise match date and internal match ID provide
    a deterministic fallback.
    """

    def __init__(
        self,
        *,
        feature_engine: Optional[PlayerFeatureEngine] = None,
    ) -> None:
        self.feature_engine = (
            feature_engine or PlayerFeatureEngine()
        )

    def build_match_snapshot(
        self,
        db: Session,
        match_id: int,
        *,
        competition_code: Optional[str] = None,
    ) -> MatchPredictionSnapshot:
        match = (
            db.query(Match)
            .filter(Match.id == match_id)
            .first()
        )

        if match is None:
            raise ValueError(
                f"Match {match_id} was not found."
            )

        player_a = resolve_player_by_name(
            db,
            match.player_a,
            record_alias=False,
        )
        player_b = resolve_player_by_name(
            db,
            match.player_b,
            record_alias=False,
        )

        if player_a is None:
            raise ValueError(
                f"Player was not found: {match.player_a}."
            )
        if player_b is None:
            raise ValueError(
                f"Player was not found: {match.player_b}."
            )

        history_a = self._load_history_before_match(
            db,
            player_id=player_a.id,
            target_match=match,
            competition_code=competition_code,
        )
        history_b = self._load_history_before_match(
            db,
            player_id=player_b.id,
            target_match=match,
            competition_code=competition_code,
        )

        return self.build_snapshot_from_history(
            db,
            match=match,
            player_a=player_a,
            player_b=player_b,
            history_a=history_a,
            history_b=history_b,
            competition_code=competition_code,
        )

    def build_snapshot_from_history(
        self,
        db,
        *,
        match,
        player_a,
        player_b,
        history_a: Sequence[Tuple[object, object]],
        history_b: Sequence[Tuple[object, object]],
        competition_code: Optional[str] = None,
    ) -> MatchPredictionSnapshot:
        profile_a = self._build_feature_profile(
            player_id=player_a.id,
            rows=history_a,
            competition_code=competition_code,
        )
        profile_b = self._build_feature_profile(
            player_id=player_b.id,
            rows=history_b,
            competition_code=competition_code,
        )

        snapshot_a = self._build_player_snapshot(
            db,
            player=player_a,
            features=profile_a,
        )
        snapshot_b = self._build_player_snapshot(
            db,
            player=player_b,
            features=profile_b,
        )

        momentum_edge = (
            round(
                snapshot_a.momentum_score
                - snapshot_b.momentum_score,
                3,
            )
            if (
                snapshot_a.momentum_score is not None
                and snapshot_b.momentum_score is not None
            )
            else None
        )

        return MatchPredictionSnapshot(
            match_id=match.id,
            match_date=(
                match.date.isoformat()
                if match.date is not None
                else None
            ),
            tournament=match.tournament,
            stage=match.stage,
            player_a=snapshot_a,
            player_b=snapshot_b,
            overall_edge=round(
                snapshot_a.overall_rating
                - snapshot_b.overall_rating,
                3,
            ),
            scoring_edge=round(
                snapshot_a.scoring_rating
                - snapshot_b.scoring_rating,
                3,
            ),
            finishing_edge=round(
                snapshot_a.finishing_rating
                - snapshot_b.finishing_rating,
                3,
            ),
            maximums_edge=round(
                snapshot_a.maximums_rating
                - snapshot_b.maximums_rating,
                3,
            ),
            form_edge=round(
                snapshot_a.form_rating
                - snapshot_b.form_rating,
                3,
            ),
            momentum_edge=momentum_edge,
            confidence_edge=round(
                snapshot_a.confidence_score
                - snapshot_b.confidence_score,
                3,
            ),
        )

    def _load_history_before_match(
        self,
        db: Session,
        *,
        player_id: int,
        target_match: Match,
        competition_code: Optional[str],
    ):
        target_performance = (
            db.query(PlayerMatchPerformance)
            .filter(
                PlayerMatchPerformance.match_id
                == target_match.id,
                PlayerMatchPerformance.player_id
                == player_id,
            )
            .first()
        )

        cutoff_observed_at = (
            target_performance.observed_at
            if target_performance is not None
            else None
        )

        query = (
            db.query(PlayerMatchPerformance, Match)
            .join(
                Match,
                Match.id
                == PlayerMatchPerformance.match_id,
            )
            .filter(
                PlayerMatchPerformance.player_id
                == player_id,
                Match.id != target_match.id,
            )
        )

        if competition_code:
            query = query.filter(
                PlayerMatchPerformance.competition_code
                == competition_code
            )

        if cutoff_observed_at is not None:
            query = query.filter(
                PlayerMatchPerformance.observed_at.isnot(
                    None
                ),
                PlayerMatchPerformance.observed_at
                < cutoff_observed_at,
            )

        if target_match.date is not None:
            query = query.filter(
                or_(
                    Match.date < target_match.date,
                    and_(
                        Match.date == target_match.date,
                        Match.id < target_match.id,
                    ),
                )
            )
        elif cutoff_observed_at is None:
            query = query.filter(
                Match.id < target_match.id
            )
        return query.order_by(
            Match.date.desc(),
            PlayerMatchPerformance.observed_at.desc(),
            PlayerMatchPerformance.created_at.desc(),
            PlayerMatchPerformance.id.desc(),
        ).all()

    def _build_feature_profile(
        self,
        *,
        player_id: int,
        rows,
        competition_code: Optional[str],
    ) -> PlayerFeatureProfile:
        performances = [
            performance
            for performance, _match in rows
        ]
        latest_match = rows[0][1] if rows else None

        return PlayerFeatureProfile(
            player_id=player_id,
            competition_code=competition_code,
            matches_available=len(performances),
            latest_match_id=(
                latest_match.id
                if latest_match is not None
                else None
            ),
            latest_match_date=(
                latest_match.date.isoformat()
                if (
                    latest_match is not None
                    and latest_match.date is not None
                )
                else None
            ),
            recent_form=tuple(
                "W" if performance.won_match else "L"
                for performance in performances[:10]
                if performance.won_match is not None
            ),
            momentum_score=(
                self.feature_engine._momentum_score(
                    performances[:5]
                )
            ),
            confidence_score=(
                self.feature_engine._confidence_score(
                    performances
                )
            ),
            windows={
                window: self.feature_engine._build_window(
                    performances[:window],
                    window,
                )
                for window in (5, 10, 20)
            },
        )

    @staticmethod
    def _build_player_snapshot(
        db,
        *,
        player,
        features: PlayerFeatureProfile,
    ) -> PlayerPredictionSnapshot:
        class StaticFeatureEngine:
            def build_player_profile(
                self,
                db,
                player_id,
                *,
                competition_code=None,
            ):
                return features

        rating = PlayerRatingEngine(
            feature_engine=StaticFeatureEngine()
        ).build_player_rating(
            db,
            player.id,
            competition_code=features.competition_code,
        )

        window_5 = features.windows[5]
        window_10 = features.windows[10]
        window_20 = features.windows[20]

        return PlayerPredictionSnapshot(
            player_id=player.id,
            player_name=player.name,
            overall_rating=rating.overall_rating,
            scoring_rating=rating.scoring_rating,
            finishing_rating=rating.finishing_rating,
            maximums_rating=rating.maximums_rating,
            form_rating=rating.form_rating,
            momentum_score=rating.momentum_score,
            confidence_score=rating.confidence_score,
            matches_available=rating.matches_available,
            latest_match_date=features.latest_match_date,
            last_5_wins=window_5.wins,
            last_5_matches=window_5.matches,
            last_10_wins=window_10.wins,
            last_10_matches=window_10.matches,
            last_20_wins=window_20.wins,
            last_20_matches=window_20.matches,
            last_10_average=(
                window_10.average_three_dart_average
            ),
            last_10_180s_per_match=(
                window_10.scores_180_per_match
            ),
            last_10_checkout_percentage=(
                window_10.calculated_checkout_percentage
            ),
            last_10_leg_difference=(
                window_10.leg_difference
            ),
        )
