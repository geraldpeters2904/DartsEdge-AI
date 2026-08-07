from __future__ import annotations

import sys
from typing import Optional

from app.db import SessionLocal
from app.services.transparent_v3_feature_contribution import (
    TransparentV3FeatureContributionLaboratory,
)


def _metric(
    value: Optional[float],
    *,
    suffix: str = "",
) -> str:
    if value is None:
        return "—"

    return f"{value:.6f}{suffix}"


def _importance_bar(
    value: float,
    *,
    width: int = 16,
) -> str:
    magnitude = min(
        abs(float(value)) * 200.0,
        float(width),
    )

    filled = round(magnitude)

    if value > 0:
        marker = "+"
    elif value < 0:
        marker = "-"
    else:
        marker = " "

    return (
        marker
        + "█" * filled
        + "░" * (width - filled)
    )


def model_contribution_v3_command(
    args,
    *,
    laboratory: Optional[
        TransparentV3FeatureContributionLaboratory
    ] = None,
    session_factory=SessionLocal,
) -> int:
    laboratory = (
        laboratory
        or TransparentV3FeatureContributionLaboratory()
    )

    db = session_factory()

    try:
        report = laboratory.analyse(
            db,
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
    print("=" * 100)
    print(
        "DartsEdge Transparent v3 "
        "Feature Contribution Laboratory"
    )
    print("=" * 100)
    print(
        f"Model             : "
        f"{report.model_version}"
    )
    print(
        f"Offset            : "
        f"{report.offset}"
    )
    print(
        f"Matches evaluated : "
        f"{report.matches_evaluated}"
    )
    print(
        f"Baseline accuracy : "
        f"{_metric(report.baseline_accuracy, suffix='%')}"
    )
    print(
        f"Baseline Brier    : "
        f"{_metric(report.baseline_brier_score)}"
    )
    print(
        f"Baseline log loss : "
        f"{_metric(report.baseline_log_loss)}"
    )
    print()

    print(
        f"{'Feature':<27}"
        f"{'Acc drop':>12}"
        f"{'Brier +':>12}"
        f"{'Log loss +':>13}"
        f"{'Importance':>14}"
        f"  {'Impact':<17}"
    )
    print("-" * 100)

    for item in report.features:
        print(
            f"{item.feature_name:<27}"
            f"{_metric(item.accuracy_drop, suffix='%'):>12}"
            f"{_metric(item.brier_increase):>12}"
            f"{_metric(item.log_loss_increase):>13}"
            f"{item.importance_score:>14.6f}"
            f"  {_importance_bar(item.importance_score)}"
        )

    helpful = sum(
        int(item.helpful)
        for item in report.features
    )

    harmful = sum(
        int(item.harmful)
        for item in report.features
    )

    neutral = (
        len(report.features)
        - helpful
        - harmful
    )

    print()
    print(
        f"Helpful features  : {helpful}"
    )
    print(
        f"Harmful features  : {harmful}"
    )
    print(
        f"Neutral features  : {neutral}"
    )
    print("=" * 100)

    return 0


def register_contribution_v3_command(
    model_commands,
) -> None:
    contribution = model_commands.add_parser(
        "contribution-v3",
        help=(
            "Measure Transparent v3 feature "
            "importance by disabling one plugin "
            "at a time."
        ),
    )

    contribution.add_argument(
        "--offset",
        type=int,
        default=1000,
        help="Completed-match offset.",
    )

    contribution.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Number of completed matches.",
    )

    contribution.add_argument(
        "--competition",
        default=None,
        help=(
            "Optional competition-code filter."
        ),
    )

    contribution.set_defaults(
        func=model_contribution_v3_command
    )
