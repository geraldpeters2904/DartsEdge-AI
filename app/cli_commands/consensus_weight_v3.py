from __future__ import annotations

import sys
from typing import Optional

from app.db import SessionLocal
from app.services.transparent_v3_weight_consensus import (
    TransparentV3WeightConsensusOptimiser,
)


def _metric(
    value: Optional[float],
    *,
    suffix: str = "",
) -> str:
    if value is None:
        return "—"

    return f"{value:.6f}{suffix}"


def model_consensus_weight_v3_command(
    args,
    *,
    optimiser: Optional[
        TransparentV3WeightConsensusOptimiser
    ] = None,
    session_factory=SessionLocal,
) -> int:
    optimiser = (
        optimiser
        or TransparentV3WeightConsensusOptimiser()
    )

    db = session_factory()

    try:
        report = optimiser.optimise(
            db,
            feature_name=args.feature,
            candidate_weights=args.weights,
            training_offsets=(
                args.training_offsets
            ),
            validation_offsets=(
                args.validation_offsets
            ),
            training_limit=(
                args.training_limit
            ),
            validation_limit=(
                args.validation_limit
            ),
            minimum_consensus=(
                args.minimum_consensus
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
    print("=" * 96)
    print(
        "DartsEdge Transparent v3 "
        "Weight Consensus Laboratory"
    )
    print("=" * 96)
    print(
        f"Feature             : "
        f"{report.feature_name}"
    )
    print(
        f"Current weight      : "
        f"{report.current_weight:.6f}"
    )
    print(
        f"Splits completed    : "
        f"{report.splits_completed}"
    )
    print()

    print(
        f"{'Training':>10}"
        f"{'Validation':>12}"
        f"{'Weight':>12}"
        f"{'Accepted':>12}"
        f"{'Accuracy Δ':>14}"
        f"{'Brier gain':>14}"
        f"{'Log-loss gain':>16}"
    )
    print("-" * 96)

    for split in report.splits:
        print(
            f"{split.training_offset:>10}"
            f"{split.validation_offset:>12}"
            f"{split.recommended_weight:>12.4f}"
            f"{'yes' if split.accepted else 'no':>12}"
            f"{_metric(split.validation_accuracy_change, suffix='%'):>14}"
            f"{_metric(split.validation_brier_change):>14}"
            f"{_metric(split.validation_log_loss_change):>16}"
        )

    print()
    print(
        f"Accepted splits     : "
        f"{report.accepted_splits}"
    )
    print(
        f"Consensus weight    : "
        f"{report.consensus_weight if report.consensus_weight is not None else '—'}"
    )
    print(
        f"Consensus votes     : "
        f"{report.consensus_votes}/"
        f"{report.splits_completed}"
    )
    print(
        f"Consensus           : "
        f"{report.consensus_percentage:.1f}%"
    )
    print(
        f"Confidence          : "
        f"{report.confidence}"
    )
    print(
        f"Promotion           : "
        f"{'RECOMMENDED' if report.promotion_recommended else 'NOT RECOMMENDED'}"
    )
    print(
        f"Reason              : "
        f"{report.reason}"
    )
    print("=" * 96)

    return 0


def register_consensus_weight_v3_command(
    model_commands,
) -> None:
    command = model_commands.add_parser(
        "consensus-weight-v3",
        help=(
            "Optimise one Transparent v3 "
            "feature across multiple independent "
            "training and validation splits."
        ),
    )

    command.add_argument(
        "--feature",
        required=True,
    )

    command.add_argument(
        "--weights",
        nargs="+",
        type=float,
        required=True,
    )

    command.add_argument(
        "--training-offsets",
        nargs="+",
        type=int,
        required=True,
    )

    command.add_argument(
        "--validation-offsets",
        nargs="+",
        type=int,
        required=True,
    )

    command.add_argument(
        "--training-limit",
        type=int,
        default=500,
    )

    command.add_argument(
        "--validation-limit",
        type=int,
        default=500,
    )

    command.add_argument(
        "--minimum-consensus",
        type=float,
        default=0.67,
    )

    command.add_argument(
        "--competition",
        default=None,
    )

    command.set_defaults(
        func=model_consensus_weight_v3_command
    )
