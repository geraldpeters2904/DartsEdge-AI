from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.player import Player
from app.services.player_name_service import (
    resolve_player_by_name,
)
from app.services.prediction_model_registry import (
    PredictionModelRegistry,
    prediction_model_registry,
)
from app.services.prediction_snapshot_engine import (
    MatchPredictionSnapshot,
    PredictionSnapshotEngine,
)
from app.services.transparent_prediction_engine import (
    MatchWinPrediction,
)


@dataclass(frozen=True)
class LaboratoryFactor:
    feature: str
    favoured_player: Optional[str]
    raw_edge: Optional[float]
    weighted_score: float


@dataclass(frozen=True)
class PredictionLaboratoryReport:
    model_name: str
    model_version: str

    match_id: Optional[int]
    match_date: Optional[str]
    tournament: Optional[str]
    stage: Optional[str]

    snapshot: MatchPredictionSnapshot
    prediction: MatchWinPrediction

    strongest_factors: Tuple[LaboratoryFactor, ...]
    opposing_factors: Tuple[LaboratoryFactor, ...]


class PredictionLaboratoryService:
    """
    Build an explainable player-v-player prediction report.

    The service supports an existing fixture or an ad-hoc comparison. For
    historical fixtures, PredictionSnapshotEngine enforces a pre-match cutoff.
    For ad-hoc comparisons, current warehouse history is used.
    """

    def __init__(
        self,
        *,
        snapshot_engine: Optional[
            PredictionSnapshotEngine
        ] = None,
        model_registry: Optional[
            PredictionModelRegistry
        ] = None,
    ) -> None:
        self.snapshot_engine = (
            snapshot_engine
            or PredictionSnapshotEngine()
        )
        self.model_registry = (
            model_registry
            or prediction_model_registry
        )

    def analyse_match(
        self,
        db: Session,
        match_id: int,
        *,
        model_name: Optional[str] = None,
        competition_code: Optional[str] = None,
    ) -> PredictionLaboratoryReport:
        snapshot = (
            self.snapshot_engine
            .build_match_snapshot(
                db,
                match_id,
                competition_code=competition_code,
            )
        )

        return self._build_report(
            snapshot=snapshot,
            model_name=model_name,
        )

    def compare_players(
        self,
        db: Session,
        *,
        player_a_name: str,
        player_b_name: str,
        model_name: Optional[str] = None,
        competition_code: Optional[str] = None,
    ) -> PredictionLaboratoryReport:
        player_a = resolve_player_by_name(
            db,
            player_a_name,
            record_alias=False,
        )
        player_b = resolve_player_by_name(
            db,
            player_b_name,
            record_alias=False,
        )

        if player_a is None:
            raise ValueError(
                f"Player was not found: {player_a_name}."
            )
        if player_b is None:
            raise ValueError(
                f"Player was not found: {player_b_name}."
            )
        if player_a.id == player_b.id:
            raise ValueError(
                "Choose two different players."
            )

        history_a = self._load_current_history(
            db,
            player_a.id,
            competition_code=competition_code,
        )
        history_b = self._load_current_history(
            db,
            player_b.id,
            competition_code=competition_code,
        )

        synthetic_match = Match(
            player_a=player_a.name,
            player_b=player_b.name,
            tournament="Prediction Laboratory",
            stage="Ad hoc",
            status="scheduled",
        )
        synthetic_match.id = 0
        synthetic_match.date = None

        snapshot = (
            self.snapshot_engine
            .build_snapshot_from_history(
                db,
                match=synthetic_match,
                player_a=player_a,
                player_b=player_b,
                history_a=history_a,
                history_b=history_b,
                competition_code=competition_code,
            )
        )

        return self._build_report(
            snapshot=snapshot,
            model_name=model_name,
        )

    def _load_current_history(
        self,
        db: Session,
        player_id: int,
        *,
        competition_code: Optional[str],
    ):
        from app.models.player_match_performance import (
            PlayerMatchPerformance,
        )

        query = (
            db.query(
                PlayerMatchPerformance,
                Match,
            )
            .join(
                Match,
                Match.id
                == PlayerMatchPerformance.match_id,
            )
            .filter(
                PlayerMatchPerformance.player_id
                == player_id
            )
        )

        if competition_code:
            query = query.filter(
                PlayerMatchPerformance.competition_code
                == competition_code
            )

        return query.order_by(
            Match.date.desc(),
            PlayerMatchPerformance.observed_at.desc(),
            PlayerMatchPerformance.created_at.desc(),
            PlayerMatchPerformance.id.desc(),
        ).all()

    def _build_report(
        self,
        *,
        snapshot: MatchPredictionSnapshot,
        model_name: Optional[str],
    ) -> PredictionLaboratoryReport:
        registered = (
            self.model_registry
            .get_registered(model_name)
        )
        prediction = registered.model.predict(
            snapshot
        )

        factors = tuple(
            LaboratoryFactor(
                feature=item.feature,
                favoured_player=(
                    snapshot.player_a.player_name
                    if item.weighted_score > 0
                    else (
                        snapshot.player_b.player_name
                        if item.weighted_score < 0
                        else None
                    )
                ),
                raw_edge=item.raw_edge,
                weighted_score=item.weighted_score,
            )
            for item in prediction.contributions
            if item.weighted_score != 0
        )

        ordered = sorted(
            factors,
            key=lambda factor: abs(
                factor.weighted_score
            ),
            reverse=True,
        )

        winner = prediction.predicted_winner

        strongest = tuple(
            factor
            for factor in ordered
            if factor.favoured_player == winner
        )[:3]

        opposing = tuple(
            factor
            for factor in ordered
            if (
                factor.favoured_player is not None
                and factor.favoured_player != winner
            )
        )[:3]

        return PredictionLaboratoryReport(
            model_name=registered.name,
            model_version=registered.version,
            match_id=(
                snapshot.match_id
                if snapshot.match_id > 0
                else None
            ),
            match_date=snapshot.match_date,
            tournament=snapshot.tournament,
            stage=snapshot.stage,
            snapshot=snapshot,
            prediction=prediction,
            strongest_factors=strongest,
            opposing_factors=opposing,
        )
