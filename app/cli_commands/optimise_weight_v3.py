from __future__ import annotations

import sys
from typing import Optional

from app.db import SessionLocal
from app.services.transparent_v3_single_weight_optimiser import (
    TransparentV3SingleWeightOptimiser,
)


def _metric(
    value: Optional[float],
    *,
    suffix: str = "",
) -> str:
    if value is None:
        return "—"

    return f"{value:.6f}{suffix}"


def model_optimise_weight_v3_command(
    args,
    *,
    optimiser: Optional[
        TransparentV3SingleWeightOptimiser
    ] = None,
    session_factory=SessionLocal,
) -> int:
    optimiser = (
        optimiser
        or TransparentV3SingleWeightOptimiser()
    )

    db = session_factory()

    try:
        report = optimiser.optimise(
            db,
            feature_name=args.feature,
            candidate_weights=args.weights,
            training_offset=(
                args.training_offset
            ),
            training_limit=(
                args.training_limit
            ),
            validation_offset=(
                args.validation_offset
            ),
            validation_limit=(
                args.validation_limit
            ),
            competition_code=(
                args.competition
            ),
        )
    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 1
    finally:
        db.close()

    print()
    print("=" * 88)
    print(
        "DartsEdge Transparent v3 "
        "Single-Feature Weight Optimiser"
    )
    print("=" * 88)
    print(
        f"Feature           : "
        f"{report.feature_name}"
    )
    print(
        f"Current weight    : "
        f"{report.current_weight:.6f}"
    )
    print(
        f"Training sample   : "
        f"offset={report.training_offset}, "
        f"matches={report.training_matches}"
    )
    print(
        f"Validation sample : "
        f"offset={report.validation_offset}, "
        f"matches={report.validation_matches}"
    )
    print()

    print("Training")
    print("-" * 88)
    print(
        f"{'Weight':>10}"
        f"{'Accuracy':>15}"
        f"{'Brier':>15}"
        f"{'Log loss':>15}"
        f"{'Selected':>14}"
    )

    results = {
        item.weight: item
        for item in (
            report.training_baseline,
            *report.training_candidates,
        )
    }

    for weight in sorted(results):
        item = results[weight]

        print(
            f"{item.weight:>10.4f}"
            f"{_metric(item.accuracy, suffix='%'):>15}"
            f"{_metric(item.brier_score):>15}"
            f"{_metric(item.log_loss):>15}"
            f"{'*' if item.weight == report.training_winner.weight else '':>14}"
        )

    print()
    print("Hold-out validation")
    print("-" * 88)
    print(
        f"{'Version':<16}"
        f"{'Weight':>10}"
        f"{'Accuracy':>15}"
        f"{'Brier':>15}"
        f"{'Log loss':>15}"
    )

    baseline = report.validation_baseline
    candidate = report.validation_candidate

    print(
        f"{'Current':<16}"
        f"{baseline.weight:>10.4f}"
        f"{_metric(baseline.accuracy, suffix='%'):>15}"
        f"{_metric(baseline.brier_score):>15}"
        f"{_metric(baseline.log_loss):>15}"
    )

    print(
        f"{'Candidate':<16}"
        f"{candidate.weight:>10.4f}"
        f"{_metric(candidate.accuracy, suffix='%'):>15}"
        f"{_metric(candidate.brier_score):>15}"
        f"{_metric(candidate.log_loss):>15}"
    )

    print()
    print(
        f"Recommendation    : "
        f"{'ACCEPT' if report.recommendation_accepted else 'KEEP CURRENT'}"
    )
    print(
        f"Recommended weight: "
        f"{report.recommended_weight:.6f}"
    )
    print(
        f"Reason            : "
        f"{report.recommendation_reason}"
    )
    print("=" * 88)

    return 0


def register_optimise_weight_v3_command(
    model_commands,
) -> None:
    command = model_commands.add_parser(
        "optimise-weight-v3",
        help=(
            "Optimise one Transparent v3 "
            "feature weight using training "
            "and hold-out samples."
        ),
    )

    command.add_argument(
        "--feature",
        required=True,
        help="Transparent v3 feature name.",
    )

    command.add_argument(
        "--weights",
        nargs="+",
        type=float,
        required=True,
        help="Candidate weights to test.",
    )

    command.add_argument(
        "--training-offset",
        type=int,
        default=1000,
    )

    command.add_argument(
        "--training-limit",
        type=int,
        default=500,
    )

    command.add_argument(
        "--validation-offset",
        type=int,
        default=2500,
    )

    command.add_argument(
        "--validation-limit",
        type=int,
        default=500,
    )

    command.add_argument(
        "--competition",
        default=None,
    )

    command.set_defaults(
        func=model_optimise_weight_v3_command
    )
