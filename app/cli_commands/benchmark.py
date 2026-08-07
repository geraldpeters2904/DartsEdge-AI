from __future__ import annotations

import sys
from typing import Optional

from app.db import SessionLocal
from app.services.model_benchmark_laboratory import (
    ModelBenchmarkLaboratory,
)


def _metric(
    value: Optional[float],
    *,
    suffix: str = "",
) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}{suffix}"


def model_benchmark_command(
    args,
    *,
    laboratory: Optional[
        ModelBenchmarkLaboratory
    ] = None,
    session_factory=SessionLocal,
) -> int:
    laboratory = (
        laboratory
        or ModelBenchmarkLaboratory()
    )
    db = session_factory()

    try:
        report = laboratory.benchmark(
            db,
            model_names=(
                args.models
                if args.models
                else None
            ),
            start_offset=args.offset,
            window_size=args.window_size,
            windows=args.windows,
            step_size=args.step,
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
    print("DartsEdge Benchmark Laboratory")
    print("=" * 76)
    print(
        f"Starting offset   : "
        f"{report.starting_offset}"
    )
    print(
        f"Window size       : "
        f"{report.window_size}"
    )
    print(
        f"Step size         : "
        f"{report.step_size}"
    )
    print(
        f"Windows completed : "
        f"{report.windows_completed}"
    )
    print()

    for summary in report.model_summaries:
        print("-" * 76)
        print(
            f"{summary.model_name} "
            f"({summary.model_version})"
        )
        print(
            "Average accuracy  : "
            f"{_metric(summary.average_accuracy, suffix='%')}"
        )
        print(
            "Median accuracy   : "
            f"{_metric(summary.median_accuracy, suffix='%')}"
        )
        print(
            "Accuracy stdev    : "
            f"{_metric(summary.accuracy_standard_deviation)}"
        )
        print(
            "Best / worst      : "
            f"{_metric(summary.best_accuracy, suffix='%')} / "
            f"{_metric(summary.worst_accuracy, suffix='%')}"
        )
        print(
            "Accuracy wins     : "
            f"{summary.accuracy_window_wins}"
        )
        print(
            "Average Brier     : "
            f"{_metric(summary.average_brier_score)}"
        )
        print(
            "Brier wins        : "
            f"{summary.brier_window_wins}"
        )
        print(
            "Average log loss  : "
            f"{_metric(summary.average_log_loss)}"
        )
        print(
            "Log-loss wins     : "
            f"{summary.log_loss_window_wins}"
        )

    print()
    print("-" * 76)
    print(
        "Best accuracy     : "
        f"{report.best_accuracy_model or '—'}"
    )
    print(
        "Best Brier        : "
        f"{report.best_brier_model or '—'}"
    )
    print(
        "Best log loss     : "
        f"{report.best_log_loss_model or '—'}"
    )
    print("=" * 76)

    return 0


def register_benchmark_command(
    model_commands,
) -> None:
    benchmark = model_commands.add_parser(
        "benchmark",
        help=(
            "Benchmark registered models over "
            "multiple historical windows."
        ),
    )
    benchmark.add_argument(
        "--models",
        nargs="*",
        default=None,
        help=(
            "Specific registered model names."
        ),
    )
    benchmark.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Starting completed-match offset.",
    )
    benchmark.add_argument(
        "--window-size",
        type=int,
        default=200,
        help="Matches per benchmark window.",
    )
    benchmark.add_argument(
        "--windows",
        type=int,
        default=10,
        help="Number of windows to evaluate.",
    )
    benchmark.add_argument(
        "--step",
        type=int,
        default=None,
        help=(
            "Offset step between windows. "
            "Defaults to the window size."
        ),
    )
    benchmark.add_argument(
        "--competition",
        default=None,
        help=(
            "Optional competition-code filter."
        ),
    )
    benchmark.set_defaults(
        func=model_benchmark_command
    )
