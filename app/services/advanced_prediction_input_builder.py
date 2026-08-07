from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.player import Player
from app.services.advanced_player_feature_engine import (
    AdvancedPlayerFeatureEngine,
)
from app.services.player_rating_engine import (
    PlayerRatingEngine,
)
from app.services.transparent_prediction_engine_v2 import (
    AdvancedMatchPredictionInput,
    AdvancedPlayerPredictionInput,
)


class AdvancedPredictionInputBuilder:
    """
    Build current player-v-player inputs for Transparent Model v2.

    This initial builder is intended for live/ad-hoc comparisons. Historical
    back-testing integration will add the same strict cutoff behaviour used by
    PredictionSnapshotEngine before v2 is compared across the archive.
    """

    def __init__(
        self,
        *,
        feature_engine: Optional[
            AdvancedPlayerFeatureEngine
        ] = None,
        rating_engine: Optional[
            PlayerRatingEngine
        ] = None,
    ) -> None:
        self.feature_engine = (
            feature_engine
            or AdvancedPlayerFeatureEngine()
        )
        self.rating_engine = (
            rating_engine
            or PlayerRatingEngine()
        )

    def build(
        self,
        db: Session,
        *,
        player_a: Player,
        player_b: Player,
        match_id: int = 0,
        competition_code: Optional[str] = None,
    ) -> AdvancedMatchPredictionInput:
        return AdvancedMatchPredictionInput(
            match_id=match_id,
            player_a=self._player(
                db,
                player=player_a,
                competition_code=competition_code,
            ),
            player_b=self._player(
                db,
                player=player_b,
                competition_code=competition_code,
            ),
        )

    def _player(
        self,
        db: Session,
        *,
        player: Player,
        competition_code: Optional[str],
    ) -> AdvancedPlayerPredictionInput:
        rating = self.rating_engine.build_player_rating(
            db,
            player.id,
            competition_code=competition_code,
        )
        advanced = self.feature_engine.build_player_profile(
            db,
            player.id,
            competition_code=competition_code,
        )

        return AdvancedPlayerPredictionInput(
            player_id=player.id,
            player_name=player.name,
            overall_rating=rating.overall_rating,
            scoring_rating=rating.scoring_rating,
            finishing_rating=rating.finishing_rating,
            maximums_rating=rating.maximums_rating,
            form_rating=rating.form_rating,
            confidence_score=rating.confidence_score,
            advanced_features=advanced,
        )
