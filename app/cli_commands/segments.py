from __future__ import annotations

import sys
from typing import Optional

from app.db import SessionLocal
from app.services.model_segment_laboratory import (
    ModelSegmentLaboratory,
)


def _metric(
    value: Optional[float],
    *,
    suffix: str = "",
) -> str:
    if value is None:
        return "—"

    return f"{value:.3f}{suffix}"


def model_segments_command(
    args,
    *,
    laboratory: Optional[
        ModelSegmentLaboratory
    ] = None,
    session_factory=SessionLocal,
) -> int:
    laboratory = (
        laboratory
        or ModelSegmentLaboratory()
    )
    db = session_factory()

    try:
        report = laboratory.compare(
            db,
            model_names=(
                args.models
                if args.models
                else None
            ),
            offset=args.offset,
            limit=args.limit,
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
    print("=" * 84)
    print("DartsEdge Model Segment Laboratory")
    print("=" * 84)
    print(
        f"Matches selected  : "
        f"{report.matches_selected}"
    )

    for summary in report.model_summaries:
        print()
        print("-" * 84)
        print(
            f"{summary.model_name} "
            f"({summary.model_version})"
        )
        print(
            f"Evaluated         : "
            f"{summary.matches_evaluated}"
        )

        print()
        print("Favourite strength")
        print(
            f"{'Band':<12}"
            f"{'N':>7}"
            f"{'Accuracy':>14}"
            f"{'Brier':>12}"
            f"{'Log loss':>12}"
        )

        for item in summary.favourite_bands:
            print(
                f"{item.segment_label:<12}"
                f"{item.predictions:>7}"
                f"{_metric(item.accuracy, suffix='%'):>14}"
                f"{_metric(item.average_brier_score):>12}"
                f"{_metric(item.average_log_loss):>12}"
            )

        print()
        print("Confidence")
        print(
            f"{'Band':<12}"
            f"{'N':>7}"
            f"{'Accuracy':>14}"
            f"{'Brier':>12}"
            f"{'Log loss':>12}"
        )

        for item in summary.confidence_bands:
            print(
                f"{item.segment_label:<12}"
                f"{item.predictions:>7}"
                f"{_metric(item.accuracy, suffix='%'):>14}"
                f"{_metric(item.average_brier_score):>12}"
                f"{_metric(item.average_log_loss):>12}"
            )

        print()
        print("Stage")
        print(
            f"{'Stage':<22}"
            f"{'N':>7}"
            f"{'Accuracy':>14}"
            f"{'Brier':>12}"
            f"{'Log loss':>12}"
        )

        for item in summary.stages:
            print(
                f"{item.segment_label:<22}"
                f"{item.predictions:>7}"
                f"{_metric(item.accuracy, suffix='%'):>14}"
                f"{_metric(item.average_brier_score):>12}"
                f"{_metric(item.average_log_loss):>12}"
            )

    print("=" * 84)

    return 0


def register_segments_command(
    model_commands,
) -> None:
    segments = model_commands.add_parser(
        "segments",
        help=(
            "Compare models by favourite, "
            "confidence and stage segments."
        ),
    )
    segments.add_argument(
        "--models",
        nargs="*",
        default=None,
        help=(
            "Specific registered model names."
        ),
    )
    segments.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Completed-match offset.",
    )
    segments.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Number of completed matches.",
    )
    segments.add_argument(
        "--competition",
        default=None,
        help=(
            "Optional competition-code filter."
        ),
    )
    segments.set_defaults(
        func=model_segments_command
    )
