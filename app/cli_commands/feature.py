from __future__ import annotations

import sys
from typing import Optional

from app.db import SessionLocal
from app.services.feature_explorer_service import (
    FeatureExplorerService,
)


def _metric(
    value: Optional[float],
    *,
    suffix: str = "",
) -> str:
    if value is None:
        return "—"

    return f"{value:.3f}{suffix}"


def feature_player_command(
    args,
    *,
    service: Optional[
        FeatureExplorerService
    ] = None,
    session_factory=SessionLocal,
) -> int:
    service = (
        service or FeatureExplorerService()
    )
    db = session_factory()

    try:
        report = service.inspect_player(
            db,
            player_name=args.name,
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
    print("DartsEdge Feature Explorer")
    print("=" * 76)
    print(
        f"Player            : "
        f"{report.player_name}"
    )
    print(
        f"Matches available : "
        f"{report.matches_available}"
    )
    print(
        f"Latest match      : "
        f"{report.latest_match_id or '—'}"
    )
    print(
        f"Latest date       : "
        f"{report.latest_match_date or '—'}"
    )
    print()

    header = (
        f"{'Window':<10}"
        f"{'M':>5}"
        f"{'W-L':>9}"
        f"{'Win%':>10}"
        f"{'Avg':>10}"
        f"{'CO%':>10}"
        f"{'180/M':>10}"
        f"{'Leg +/-':>10}"
    )
    print(header)
    print("-" * len(header))

    for window in report.windows:
        print(
            f"{window.label:<10}"
            f"{window.matches:>5}"
            f"{window.wins:>4}-"
            f"{window.losses:<4}"
            f"{_metric(window.win_percentage, suffix='%'):>10}"
            f"{_metric(window.three_dart_average):>10}"
            f"{_metric(window.checkout_percentage, suffix='%'):>10}"
            f"{_metric(window.scores_180_per_match):>10}"
            f"{window.leg_difference:>10}"
        )

    print()
    print("Trends")
    print("-" * 76)

    for trend in report.trends:
        print(
            f"{trend.metric:<28}"
            f"{trend.direction:<12}"
            f"recent={_metric(trend.recent_value):>10} "
            f"baseline={_metric(trend.baseline_value):>10} "
            f"change={_metric(trend.absolute_change):>10}"
        )

    print()
    print("Throw order and pressure")
    print("-" * 76)

    last_20 = next(
        window
        for window in report.windows
        if window.label == "last_20"
    )

    print(
        "Throw-first win % : "
        f"{_metric(last_20.threw_first_win_percentage, suffix='%')}"
    )
    print(
        "Throw-second win% : "
        f"{_metric(last_20.threw_second_win_percentage, suffix='%')}"
    )
    print(
        "Deciding win %    : "
        f"{_metric(last_20.deciding_win_percentage, suffix='%')}"
    )

    print()
    print("Fatigue context")
    print("-" * 76)
    print(
        "Matches latest day: "
        f"{report.matches_on_latest_day}"
    )
    print(
        "Legs latest day   : "
        f"{report.legs_on_latest_day}"
    )
    print(
        "Hours since prior : "
        f"{_metric(report.hours_since_previous_match)}"
    )
    print(
        "Days since prior  : "
        f"{report.days_since_previous_match if report.days_since_previous_match is not None else '—'}"
    )
    print("=" * 76)

    return 0


def register_feature_commands(
    commands,
) -> None:
    feature = commands.add_parser(
        "feature",
        help="Feature exploration commands.",
    )
    feature_commands = (
        feature.add_subparsers(
            dest="feature_command"
        )
    )

    player = (
        feature_commands.add_parser(
            "player",
            help=(
                "Inspect advanced features for "
                "one player."
            ),
        )
    )
    player.add_argument(
        "--name",
        required=True,
        help="Player name.",
    )
    player.add_argument(
        "--competition",
        default=None,
        help=(
            "Optional competition-code filter."
        ),
    )
    player.set_defaults(
        func=feature_player_command
    )
