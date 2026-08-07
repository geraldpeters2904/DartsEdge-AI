from __future__ import annotations

import sys
from typing import Optional

from app.db import SessionLocal
from app.services.transparent_v32_feature_tuning_laboratory import (
    TransparentV32FeatureTuningLaboratory,
)


def _metric(
    value: Optional[float],
    *,
    suffix: str = "",
) -> str:
    if value is None:
        return "—"

    return f"{value:.6f}{suffix}"


def model_tune_features_v32_command(
    args,
    *,
    laboratory=None,
    session_factory=SessionLocal,
) -> int:
    laboratory = (
        laboratory
        or TransparentV32FeatureTuningLaboratory()
    )

    db = session_factory()

    try:
        report = laboratory.tune(
            db,
            feature_names=(
                args.features
                if args.features
                else None
            ),
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
    print("=" * 108)
    print(
        "DartsEdge Transparent v3.2 "
        "Feature Tuning Laboratory"
    )
    print("=" * 108)
    print(
        f"Model              : "
        f"{report.model_version}"
    )

    for item in report.recommendations:
        print()
        print("-" * 108)
        print(
            f"Feature            : "
            f"{item.feature_name}"
        )
        print(
            f"Current weight     : "
            f"{item.current_weight:.6f}"
        )
        print()

        print(
            f"{'Training':>10}"
            f"{'Validation':>12}"
            f"{'Winner':>12}"
            f"{'Accepted':>12}"
            f"{'Accuracy Δ':>14}"
            f"{'Brier gain':>14}"
            f"{'Log-loss gain':>16}"
        )

        for split in item.splits:
            print(
                f"{split.training_offset:>10}"
                f"{split.validation_offset:>12}"
                f"{split.training_winner:>12.4f}"
                f"{'yes' if split.accepted else 'no':>12}"
                f"{_metric(split.validation_accuracy_change, suffix='%'):>14}"
                f"{_metric(split.validation_brier_gain):>14}"
                f"{_metric(split.validation_log_loss_gain):>16}"
            )

        print()
        print(
            f"Consensus weight   : "
            f"{item.consensus_weight if item.consensus_weight is not None else '—'}"
        )
        print(
            f"Consensus votes    : "
            f"{item.consensus_votes}/"
            f"{item.splits_completed}"
        )
        print(
            f"Consensus          : "
            f"{item.consensus_percentage:.1f}%"
        )
        print(
            f"Confidence         : "
            f"{item.confidence}"
        )
        print(
            f"Promotion          : "
            f"{'RECOMMENDED' if item.promotion_recommended else 'NOT RECOMMENDED'}"
        )
        print(
            f"Reason             : "
            f"{item.reason}"
        )

    print("=" * 108)

    return 0


def register_tune_features_v32_command(
    model_commands,
) -> None:
    command = model_commands.add_parser(
        "tune-features-v32",
        help=(
            "Tune Transparent v3.2 feature "
            "weights across repeated training "
            "and hold-out splits."
        ),
    )

    command.add_argument(
        "--features",
        nargs="*",
        default=None,
        help=(
            "Specific v3.2 features. "
            "Defaults to all features."
        ),
    )

    command.add_argument(
        "--training-offsets",
        nargs="+",
        type=int,
        default=[
            500,
            1000,
            1500,
        ],
    )

    command.add_argument(
        "--validation-offsets",
        nargs="+",
        type=int,
        default=[
            2000,
            2500,
            3000,
        ],
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
        func=model_tune_features_v32_command
    )
