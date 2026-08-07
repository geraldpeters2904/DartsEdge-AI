from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.advanced_player_feature_engine import (
    AdvancedPlayerFeatureEngine,
)
from app.services.player_rating_engine import (
    PlayerRatingEngine,
)
from app.services.prediction_snapshot_engine import (
    PredictionSnapshotEngine,
)
from app.services.transparent_prediction_engine_v2 import (
    AdvancedMatchPredictionInput,
    AdvancedPlayerPredictionInput,
)


class AdvancedHistoricalSnapshotEngine:
    """
    Build Transparent v2 inputs using only pre-match historical data.

    The underlying row selection reuses PredictionSnapshotEngine's historical
    cutoff logic, preserving the same no-look-ahead guarantee as v1.
    """

    def __init__(
        self,
        *,
        base_snapshot_engine: Optional[
            PredictionSnapshotEngine
        ] = None,
        advanced_feature_engine: Optional[
            AdvancedPlayerFeatureEngine
        ] = None,
    ) -> None:
        self.base_snapshot_engine = (
            base_snapshot_engine
            or PredictionSnapshotEngine()
        )
        self.advanced_feature_engine = (
            advanced_feature_engine
            or AdvancedPlayerFeatureEngine()
        )

    def build_match_snapshot(
        self,
        db: Session,
        match_id: int,
        *,
        competition_code: Optional[str] = None,
    ) -> AdvancedMatchPredictionInput:
        match = (
            db.query(Match)
            .filter(Match.id == match_id)
            .first()
        )

        if match is None:
            raise ValueError(
                f"Match {match_id} was not found."
            )

        player_a = self.base_snapshot_engine._resolve_player(
            db,
            match.player_a,
        ) if hasattr(
            self.base_snapshot_engine,
            "_resolve_player",
        ) else None

        player_b = self.base_snapshot_engine._resolve_player(
            db,
            match.player_b,
        ) if hasattr(
            self.base_snapshot_engine,
            "_resolve_player",
        ) else None

        if player_a is None or player_b is None:
            from app.services.player_name_service import (
                resolve_player_by_name,
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

        history_a = (
            self.base_snapshot_engine
            ._load_history_before_match(
                db,
                player_id=player_a.id,
                target_match=match,
                competition_code=competition_code,
            )
        )
        history_b = (
            self.base_snapshot_engine
            ._load_history_before_match(
                db,
                player_id=player_b.id,
                target_match=match,
                competition_code=competition_code,
            )
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
        history_a,
        history_b,
        competition_code: Optional[str] = None,
    ) -> AdvancedMatchPredictionInput:
        base_a = (
            self.base_snapshot_engine
            ._build_feature_profile(
                player_id=player_a.id,
                rows=history_a,
                competition_code=competition_code,
            )
        )
        base_b = (
            self.base_snapshot_engine
            ._build_feature_profile(
                player_id=player_b.id,
                rows=history_b,
                competition_code=competition_code,
            )
        )

        rating_a = self._rating_from_profile(
            db,
            player=player_a,
            profile=base_a,
        )
        rating_b = self._rating_from_profile(
            db,
            player=player_b,
            profile=base_b,
        )

        advanced_a = (
            self.advanced_feature_engine
            .build_from_rows(
                player_id=player_a.id,
                rows=history_a,
                competition_code=competition_code,
            )
        )
        advanced_b = (
            self.advanced_feature_engine
            .build_from_rows(
                player_id=player_b.id,
                rows=history_b,
                competition_code=competition_code,
            )
        )

        return AdvancedMatchPredictionInput(
            match_id=match.id,
            player_a=AdvancedPlayerPredictionInput(
                player_id=player_a.id,
                player_name=player_a.name,
                overall_rating=(
                    rating_a.overall_rating
                ),
                scoring_rating=(
                    rating_a.scoring_rating
                ),
                finishing_rating=(
                    rating_a.finishing_rating
                ),
                maximums_rating=(
                    rating_a.maximums_rating
                ),
                form_rating=(
                    rating_a.form_rating
                ),
                confidence_score=(
                    rating_a.confidence_score
                ),
                advanced_features=advanced_a,
            ),
            player_b=AdvancedPlayerPredictionInput(
                player_id=player_b.id,
                player_name=player_b.name,
                overall_rating=(
                    rating_b.overall_rating
                ),
                scoring_rating=(
                    rating_b.scoring_rating
                ),
                finishing_rating=(
                    rating_b.finishing_rating
                ),
                maximums_rating=(
                    rating_b.maximums_rating
                ),
                form_rating=(
                    rating_b.form_rating
                ),
                confidence_score=(
                    rating_b.confidence_score
                ),
                advanced_features=advanced_b,
            ),
        )

    @staticmethod
    def _rating_from_profile(
        db,
        *,
        player,
        profile,
    ):
        class StaticFeatureEngine:
            def build_player_profile(
                self,
                db,
                player_id,
                *,
                competition_code=None,
            ):
                return profile

        return PlayerRatingEngine(
            feature_engine=StaticFeatureEngine()
        ).build_player_rating(
            db,
            player.id,
            competition_code=profile.competition_code,
        )
