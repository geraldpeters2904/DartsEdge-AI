from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.match import Match
from app.services.advanced_historical_snapshot_engine import (
    AdvancedHistoricalSnapshotEngine,
)
from app.services.current_match_enrichment_v33_validation_service import (
    CurrentMatchEnrichmentV33ValidationService,
)
from app.services.transparent_prediction_engine_v33 import (
    TransparentPredictionEngineV33,
)


@dataclass(frozen=True)
class V33DualLowHistoryConsensusBand:
    band: str
    predictions: int
    correct: int
    accuracy: Optional[float]

    average_favourite_probability: Optional[float]
    average_confidence: Optional[float]


@dataclass(frozen=True)
class V33DualLowHistoryConsensusWindow:
    offset: int
    matches_evaluated: int
    dual_low_history_matches: int

    bands: Tuple[
        V33DualLowHistoryConsensusBand,
        ...
    ]


@dataclass(frozen=True)
class V33DualLowHistoryConsensusRiskReport:
    model_version: str
    competition_code: Optional[str]

    probability_lower: float
    probability_upper: float
    history_threshold: int

    windows_completed: int
    total_dual_low_history_matches: int

    windows: Tuple[
        V33DualLowHistoryConsensusWindow,
        ...
    ]


class CurrentMatchEnrichmentV33DualLowHistoryConsensusRiskService:
    """
    Read-only diagnostic for feature-consensus risk when both
    players have extremely low pre-match history.

    Agreement bands:
    - below 80%
    - 80% to below 100%
    - exactly 100%

    No model weights, probabilities or production behaviour
    are modified.
    """

    AGREEMENT_BANDS = (
        "below_80",
        "80_to_below_100",
        "exactly_100",
    )

    def __init__(
        self,
        *,
        snapshot_engine=None,
        prediction_engine=None,
    ) -> None:
        self.snapshot_engine = (
            snapshot_engine
            or AdvancedHistoricalSnapshotEngine()
        )

        self.prediction_engine = (
            prediction_engine
            or TransparentPredictionEngineV33()
        )

    def analyse(
        self,
        db: Session,
        *,
        offsets: Iterable[int],
        window_size: int = 500,
        probability_lower: float = 65.0,
        probability_upper: float = 70.0,
        history_threshold: int = 3,
        competition_code: Optional[str] = "MODUS",
    ) -> V33DualLowHistoryConsensusRiskReport:
        offsets = tuple(
            int(value)
            for value in offsets
        )

        if not offsets:
            raise ValueError(
                "Enter at least one window offset."
            )

        if window_size <= 0:
            raise ValueError(
                "window_size must be greater than zero."
            )

        if probability_lower < 50.0:
            raise ValueError(
                "probability_lower cannot be below 50."
            )

        if probability_upper <= probability_lower:
            raise ValueError(
                "probability_upper must exceed probability_lower."
            )

        if probability_upper > 100.0:
            raise ValueError(
                "probability_upper cannot exceed 100."
            )

        if history_threshold <= 0:
            raise ValueError(
                "history_threshold must be greater than zero."
            )

        windows = tuple(
            self._analyse_window(
                db,
                offset=offset,
                window_size=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_threshold=history_threshold,
                competition_code=competition_code,
            )
            for offset in offsets
        )

        return V33DualLowHistoryConsensusRiskReport(
            model_version=(
                self.prediction_engine.MODEL_VERSION
            ),
            competition_code=competition_code,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            history_threshold=history_threshold,
            windows_completed=len(windows),
            total_dual_low_history_matches=sum(
                item.dual_low_history_matches
                for item in windows
            ),
            windows=windows,
        )

    def _analyse_window(
        self,
        db,
        *,
        offset,
        window_size,
        probability_lower,
        probability_upper,
        history_threshold,
        competition_code,
    ):
        match_ids = (
            CurrentMatchEnrichmentV33ValidationService
            ._select_match_ids(
                db,
                offset=offset,
                limit=window_size,
            )
        )

        evaluated = 0
        selected = []

        for match_id in match_ids:
            match = (
                db.query(Match)
                .filter(Match.id == match_id)
                .first()
            )

            if match is None:
                continue

            try:
                snapshot = (
                    self.snapshot_engine
                    .build_match_snapshot(
                        db,
                        match_id,
                        competition_code=competition_code,
                    )
                )

                prediction = (
                    self.prediction_engine
                    .predict(snapshot)
                )

                evaluated += 1

                favourite_probability = max(
                    float(
                        prediction.player_a_probability
                    ),
                    float(
                        prediction.player_b_probability
                    ),
                )

                if not (
                    favourite_probability >= probability_lower
                    and favourite_probability < probability_upper
                ):
                    continue

                history_a = int(
                    snapshot.player_a
                    .advanced_features
                    .matches_available
                )

                history_b = int(
                    snapshot.player_b
                    .advanced_features
                    .matches_available
                )

                if not (
                    history_a < history_threshold
                    and history_b < history_threshold
                ):
                    continue

                favourite_is_a = (
                    prediction.player_a_probability
                    >= prediction.player_b_probability
                )

                supporting = 0
                opposing = 0

                for contribution in (
                    prediction.contributions
                ):
                    weighted = float(
                        contribution.weighted_score
                    )

                    if weighted == 0.0:
                        continue

                    supports = (
                        weighted > 0.0
                        if favourite_is_a
                        else weighted < 0.0
                    )

                    if supports:
                        supporting += 1
                    else:
                        opposing += 1

                active = supporting + opposing

                agreement = (
                    supporting
                    / active
                    * 100.0
                    if active
                    else None
                )

                selected.append(
                    {
                        "agreement": agreement,
                        "correct": (
                            prediction.predicted_winner
                            == match.winner
                        ),
                        "favourite_probability": (
                            favourite_probability
                        ),
                        "confidence": float(
                            prediction.confidence
                        ),
                    }
                )

            except (ValueError, LookupError):
                continue

        bands = tuple(
            self._build_band(
                selected,
                band=band,
            )
            for band
            in self.AGREEMENT_BANDS
        )

        return V33DualLowHistoryConsensusWindow(
            offset=offset,
            matches_evaluated=evaluated,
            dual_low_history_matches=len(
                selected
            ),
            bands=bands,
        )

    @classmethod
    def _build_band(
        cls,
        selected,
        *,
        band,
    ):
        rows = tuple(
            item
            for item in selected
            if cls._in_band(
                item["agreement"],
                band,
            )
        )

        correct = sum(
            int(item["correct"])
            for item in rows
        )

        return V33DualLowHistoryConsensusBand(
            band=band,
            predictions=len(rows),
            correct=correct,
            accuracy=cls._percentage(
                correct,
                len(rows),
            ),
            average_favourite_probability=(
                cls._average(
                    item[
                        "favourite_probability"
                    ]
                    for item in rows
                )
            ),
            average_confidence=(
                cls._average(
                    item["confidence"]
                    for item in rows
                )
            ),
        )

    @staticmethod
    def _in_band(
        agreement,
        band,
    ):
        if agreement is None:
            return False

        if band == "below_80":
            return agreement < 80.0

        if band == "80_to_below_100":
            return (
                agreement >= 80.0
                and agreement < 100.0
            )

        if band == "exactly_100":
            return agreement == 100.0

        raise ValueError(
            f"Unknown agreement band: {band}."
        )

    @staticmethod
    def _average(values):
        values = tuple(
            float(value)
            for value in values
        )

        if not values:
            return None

        return round(
            sum(values)
            / len(values),
            6,
        )

    @staticmethod
    def _percentage(
        numerator,
        denominator,
    ):
        if not denominator:
            return None

        return round(
            float(numerator)
            / float(denominator)
            * 100.0,
            3,
        )
