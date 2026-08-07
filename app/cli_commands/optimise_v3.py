from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from app.db import SessionLocal
from app.services.transparent_v3_weight_optimiser import (
    TransparentV3WeightOptimiser,
)


def _metric(
    value: Optional[float],
    *,
    suffix: str = "",
) -> str:
    if value is None:
        return "—"
    return f"{value:.6f}{suffix}"


def model_optimise_v3_command(
    args,
    *,
    optimiser: Optional[
        TransparentV3WeightOptimiser
    ] = None,
    session_factory=SessionLocal,
) -> int:
    optimiser = (
        optimiser
        or TransparentV3WeightOptimiser()
    )
    db = session_factory()

    try:
        result = optimiser.optimise(
            db,
            offset=args.offset,
            limit=args.limit,
            step_sizes=args.steps,
            passes=args.passes,
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
    print("=" * 76)
    print("DartsEdge Transparent v3 Weight Optimiser")
    print("=" * 76)
    print(
        f"Matches evaluated : "
        f"{result.matches_evaluated}"
    )
    print(
        "Baseline accuracy : "
        f"{_metric(result.baseline_score.accuracy, suffix='%')}"
    )
    print(
        "Baseline Brier    : "
        f"{_metric(result.baseline_score.brier_score)}"
    )
    print(
        "Baseline log loss : "
        f"{_metric(result.baseline_score.log_loss)}"
    )
    print()
    print(
        "Best accuracy     : "
        f"{_metric(result.best_score.accuracy, suffix='%')}"
    )
    print(
        "Best Brier        : "
        f"{_metric(result.best_score.brier_score)}"
    )
    print(
        "Best log loss     : "
        f"{_metric(result.best_score.log_loss)}"
    )
    print()
    print("Best weights")
    print("-" * 76)

    for name, value in sorted(
        result.best_weights.items()
    ):
        print(
            f"{name:<28}"
            f"{value:>10.4f}"
        )

    accepted = [
        step
        for step in result.steps
        if step.accepted
    ]

    print()
    print(
        f"Accepted changes  : "
        f"{len(accepted)}"
    )
    print("=" * 76)

    if args.output:
        path = Path(
            args.output
        ).expanduser().resolve()
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                {
                    "model_version": (
                        result.model_version
                    ),
                    "matches_evaluated": (
                        result.matches_evaluated
                    ),
                    "baseline": {
                        "accuracy": (
                            result.baseline_score
                            .accuracy
                        ),
                        "brier_score": (
                            result.baseline_score
                            .brier_score
                        ),
                        "log_loss": (
                            result.baseline_score
                            .log_loss
                        ),
                    },
                    "best": {
                        "accuracy": (
                            result.best_score
                            .accuracy
                        ),
                        "brier_score": (
                            result.best_score
                            .brier_score
                        ),
                        "log_loss": (
                            result.best_score
                            .log_loss
                        ),
                    },
                    "weights": (
                        result.best_weights
                    ),
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        print(f"Saved: {path}")

    return 0


def register_optimise_v3_command(
    model_commands,
) -> None:
    optimise = model_commands.add_parser(
        "optimise-v3",
        help=(
            "Optimise Transparent v3 feature "
            "weights on historical matches."
        ),
    )
    optimise.add_argument(
        "--offset",
        type=int,
        default=1000,
        help="Completed-match offset.",
    )
    optimise.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Number of completed matches.",
    )
    optimise.add_argument(
        "--steps",
        nargs="+",
        type=float,
        default=[0.04, 0.02, 0.01],
        help=(
            "Coordinate-descent step sizes."
        ),
    )
    optimise.add_argument(
        "--passes",
        type=int,
        default=2,
        help="Maximum optimisation passes.",
    )
    optimise.add_argument(
        "--competition",
        default=None,
        help=(
            "Optional competition-code filter."
        ),
    )
    optimise.add_argument(
        "--output",
        default=None,
        help=(
            "Optional JSON output path."
        ),
    )
    optimise.set_defaults(
        func=model_optimise_v3_command
    )
