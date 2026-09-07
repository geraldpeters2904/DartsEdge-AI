from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from app.services.leg_market_validation_engine import (
    LegMarketValidationRecord,
)


@dataclass(frozen=True)
class ChronologicalFold:
    train: Tuple[LegMarketValidationRecord, ...]
    test: Tuple[LegMarketValidationRecord, ...]


def chronological_folds(
    records,
    *,
    initial_train_size,
    test_size,
):
    initial_train_size = int(initial_train_size)
    test_size = int(test_size)

    if initial_train_size <= 0:
        raise ValueError(
            "initial_train_size must be positive."
        )

    if test_size <= 0:
        raise ValueError(
            "test_size must be positive."
        )

    records = tuple(records)

    folds = []
    train_end = initial_train_size

    while train_end + test_size <= len(records):
        folds.append(
            ChronologicalFold(
                train=records[:train_end],
                test=records[
                    train_end:train_end + test_size
                ],
            )
        )
        train_end += test_size

    return tuple(folds)


def brier_score(
    probabilities,
    results,
):
    probabilities = tuple(
        float(probability)
        for probability in probabilities
    )
    results = tuple(
        int(result)
        for result in results
    )

    if len(probabilities) != len(results):
        raise ValueError(
            "probabilities and results must have equal length."
        )

    if not probabilities:
        raise ValueError(
            "probabilities and results must not be empty."
        )

    return sum(
        (probability - result) ** 2
        for probability, result in zip(
            probabilities,
            results,
        )
    ) / len(probabilities)


def fit_platt_calibration(
    probabilities,
    results,
):
    from app.services.leg_market_calibration_service import (
        PlattCalibration,
    )

    probabilities = tuple(
        float(probability)
        for probability in probabilities
    )
    results = tuple(
        int(result)
        for result in results
    )

    if len(probabilities) != len(results):
        raise ValueError(
            "probabilities and results must have equal length."
        )

    if not probabilities:
        raise ValueError(
            "probabilities and results must not be empty."
        )

    epsilon = 1e-6
    logits = tuple(
        __import__("math").log(
            min(max(probability, epsilon), 1.0 - epsilon)
            / (
                1.0
                - min(
                    max(probability, epsilon),
                    1.0 - epsilon,
                )
            )
        )
        for probability in probabilities
    )

    def candidate_score(slope, intercept):
        total = 0.0

        for log_odds, result in zip(
            logits,
            results,
        ):
            value = slope * log_odds + intercept

            if value >= 0.0:
                z = __import__("math").exp(-value)
                calibrated = 1.0 / (1.0 + z)
            else:
                z = __import__("math").exp(value)
                calibrated = z / (1.0 + z)

            total += (calibrated - result) ** 2

        return total / len(results)

    def search(
        slope_values,
        intercept_values,
        current_best=None,
    ):
        slope_values = tuple(slope_values)
        intercept_values = tuple(intercept_values)

        best = current_best

        for slope in slope_values:
            if slope < 0.0 or slope > 2.0:
                continue

            for intercept in intercept_values:
                if intercept < -2.0 or intercept > 2.0:
                    continue

                score = candidate_score(
                    slope,
                    intercept,
                )

                candidate = (
                    score,
                    slope,
                    intercept,
                )

                if best is None or candidate < best:
                    best = candidate

        return best

    # Coarse search across the full original bounds.
    best = search(
        (
            value / 10.0
            for value in range(0, 21)
        ),
        (
            value / 10.0
            for value in range(-20, 21)
        ),
    )

    # Refine around the best coarse point to 0.025,
    # matching the resolution of the original exhaustive grid.
    _, best_slope, best_intercept = best

    slope_start = max(
        0.0,
        best_slope - 0.10,
    )
    slope_end = min(
        2.0,
        best_slope + 0.10,
    )
    intercept_start = max(
        -2.0,
        best_intercept - 0.10,
    )
    intercept_end = min(
        2.0,
        best_intercept + 0.10,
    )

    slope_values = tuple(
        round(slope_start + step * 0.025, 10)
        for step in range(
            int(round(
                (slope_end - slope_start) / 0.025
            )) + 1
        )
    )
    intercept_values = tuple(
        round(intercept_start + step * 0.025, 10)
        for step in range(
            int(round(
                (intercept_end - intercept_start) / 0.025
            )) + 1
        )
    )

    best = search(
        slope_values,
        intercept_values,
        current_best=best,
    )

    _, slope, intercept = best

    return PlattCalibration(
        slope=slope,
        intercept=intercept,
    )


@dataclass(frozen=True)
class FoldEvaluation:
    train_size: int
    test_size: int
    train_hit_rate: float
    test_hit_rate: float
    raw_brier_score: float
    calibrated_brier_score: float
    constant_brier_score: float
    calibration: object


def evaluate_fold(
    train,
    test,
    *,
    probability_attr,
    result_attr,
):
    train = tuple(train)
    test = tuple(test)

    if not train:
        raise ValueError(
            "train must not be empty."
        )

    if not test:
        raise ValueError(
            "test must not be empty."
        )

    train_probabilities = tuple(
        float(getattr(record, probability_attr))
        for record in train
    )
    train_results = tuple(
        int(getattr(record, result_attr))
        for record in train
    )

    test_probabilities = tuple(
        float(getattr(record, probability_attr))
        for record in test
    )
    test_results = tuple(
        int(getattr(record, result_attr))
        for record in test
    )

    calibration = fit_platt_calibration(
        train_probabilities,
        train_results,
    )

    calibrated_test_probabilities = tuple(
        calibration.apply(probability)
        for probability in test_probabilities
    )

    train_hit_rate = (
        sum(train_results) / len(train_results)
    )
    test_hit_rate = (
        sum(test_results) / len(test_results)
    )

    constant_probabilities = tuple(
        train_hit_rate
        for _ in test_results
    )

    return FoldEvaluation(
        train_size=len(train),
        test_size=len(test),
        train_hit_rate=train_hit_rate,
        test_hit_rate=test_hit_rate,
        raw_brier_score=brier_score(
            test_probabilities,
            test_results,
        ),
        calibrated_brier_score=brier_score(
            calibrated_test_probabilities,
            test_results,
        ),
        constant_brier_score=brier_score(
            constant_probabilities,
            test_results,
        ),
        calibration=calibration,
    )


@dataclass(frozen=True)
class WalkForwardReport:
    records: int
    folds_evaluated: int
    test_observations: int
    raw_brier_score: float
    calibrated_brier_score: float
    constant_brier_score: float
    slopes: Tuple[float, ...]
    intercepts: Tuple[float, ...]
    folds: Tuple[FoldEvaluation, ...]


def evaluate_walk_forward(
    records,
    *,
    probability_attr,
    result_attr,
    initial_train_size,
    test_size,
):
    records = tuple(records)

    folds = chronological_folds(
        records,
        initial_train_size=initial_train_size,
        test_size=test_size,
    )

    if not folds:
        raise ValueError(
            "not enough records to create a walk-forward fold."
        )

    evaluations = tuple(
        evaluate_fold(
            fold.train,
            fold.test,
            probability_attr=probability_attr,
            result_attr=result_attr,
        )
        for fold in folds
    )

    test_observations = sum(
        evaluation.test_size
        for evaluation in evaluations
    )

    raw_brier_score = sum(
        evaluation.raw_brier_score
        * evaluation.test_size
        for evaluation in evaluations
    ) / test_observations

    calibrated_brier_score = sum(
        evaluation.calibrated_brier_score
        * evaluation.test_size
        for evaluation in evaluations
    ) / test_observations

    constant_brier_score = sum(
        evaluation.constant_brier_score
        * evaluation.test_size
        for evaluation in evaluations
    ) / test_observations

    return WalkForwardReport(
        records=len(records),
        folds_evaluated=len(evaluations),
        test_observations=test_observations,
        raw_brier_score=raw_brier_score,
        calibrated_brier_score=calibrated_brier_score,
        constant_brier_score=constant_brier_score,
        slopes=tuple(
            evaluation.calibration.slope
            for evaluation in evaluations
        ),
        intercepts=tuple(
            evaluation.calibration.intercept
            for evaluation in evaluations
        ),
        folds=evaluations,
    )
