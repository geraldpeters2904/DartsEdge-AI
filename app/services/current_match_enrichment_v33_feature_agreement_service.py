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
class V33FeatureAgreementBand:
    band: str
    predictions: int
    correct: int
    accuracy: Optional[float]


@dataclass(frozen=True)
class V33FeatureAgreementWindow:
    offset: int
    matches_evaluated: int
    segment_matches: int
    correct: int
    accuracy: Optional[float]

    average_supporting_features: Optional[float]
    average_opposing_features: Optional[float]
    average_agreement_percentage: Optional[float]

    agreement_bands: Tuple[
        V33FeatureAgreementBand,
        ...
    ]


@dataclass(frozen=True)
class V33FeatureAgreementReport:
    model_version: str
    competition_code: Optional[str]

    probability_lower: float
    probability_upper: float
    history_upper: int

    windows_completed: int
    total_segment_matches: int

    windows: Tuple[
        V33FeatureAgreementWindow,
        ...
    ]


class CurrentMatchEnrichmentV33FeatureAgreementService:
    """
    Read-only analysis of internal feature agreement for low-history
    transparent-v3.3 predictions.

    A feature supports the favourite when its weighted contribution
    points toward the same player as the model's predicted favourite.
    """

    AGREEMENT_BANDS = (
        (0.0, 50.0),
        (50.0, 65.0),
        (65.0, 80.0),
        (80.0, 101.0),
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
        history_upper: int = 10,
        competition_code: Optional[str] = "MODUS",
    ) -> V33FeatureAgreementReport:
        offsets = tuple(
            int(value)
            for value in offsets
        )

        if not offsets:
            raise ValueError(
                "Enter at least one window offset."
            )

        windows = tuple(
            self._analyse_window(
                db,
                offset=offset,
                window_size=window_size,
                probability_lower=probability_lower,
                probability_upper=probability_upper,
                history_upper=history_upper,
                competition_code=competition_code,
            )
            for offset in offsets
        )

        return V33FeatureAgreementReport(
            model_version=self.prediction_engine.MODEL_VERSION,
            competition_code=competition_code,
            probability_lower=probability_lower,
            probability_upper=probability_upper,
            history_upper=history_upper,
            windows_completed=len(windows),
            total_segment_matches=sum(
                item.segment_matches
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
        history_upper,
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
                    float(prediction.player_a_probability),
                    float(prediction.player_b_probability),
                )

                minimum_history = min(
                    int(
                        snapshot.player_a
                        .advanced_features
                        .matches_available
                    ),
                    int(
                        snapshot.player_b
                        .advanced_features
                        .matches_available
                    ),
                )

                if not (
                    favourite_probability >= probability_lower
                    and favourite_probability < probability_upper
                    and minimum_history < history_upper
                ):
                    continue

                favourite_is_a = (
                    prediction.player_a_probability
                    >= prediction.player_b_probability
                )

                supporting = 0
                opposing = 0

                for contribution in prediction.contributions:
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
                    supporting / active * 100.0
                    if active
                    else 0.0
                )

                selected.append(
                    {
                        "correct": (
                            prediction.predicted_winner
                            == match.winner
                        ),
                        "supporting": supporting,
                        "opposing": opposing,
                        "agreement": agreement,
                    }
                )

            except (ValueError, LookupError):
                continue

        correct = sum(
            int(item["correct"])
            for item in selected
        )

        bands = tuple(
            self._build_band(
                selected,
                lower=lower,
                upper=upper,
            )
            for lower, upper
            in self.AGREEMENT_BANDS
        )

        return V33FeatureAgreementWindow(
            offset=offset,
            matches_evaluated=evaluated,
            segment_matches=len(selected),
            correct=correct,
            accuracy=self._percentage(
                correct,
                len(selected),
            ),
            average_supporting_features=self._average(
                item["supporting"]
                for item in selected
            ),
            average_opposing_features=self._average(
                item["opposing"]
                for item in selected
            ),
            average_agreement_percentage=self._average(
                item["agreement"]
                for item in selected
            ),
            agreement_bands=bands,
        )

    @classmethod
    def _build_band(
        cls,
        selected,
        *,
        lower,
        upper,
    ):
        rows = tuple(
            item
            for item in selected
            if (
                item["agreement"] >= lower
                and item["agreement"] < upper
            )
        )

        correct = sum(
            int(item["correct"])
            for item in rows
        )

        label = (
            f"{int(lower)}-{int(upper - 1)}"
            if upper > 100
            else f"{int(lower)}-{int(upper)}"
        )

        return V33FeatureAgreementBand(
            band=label,
            predictions=len(rows),
            correct=correct,
            accuracy=cls._percentage(
                correct,
                len(rows),
            ),
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
            sum(values) / len(values),
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
