from __future__ import annotations

import sys
from typing import Optional

from app.db import SessionLocal
from app.services.warehouse_metrics_service import WarehouseMetricsService


def _percentage_bar(percentage: float, width: int = 30) -> str:
    bounded = min(max(float(percentage), 0.0), 100.0)
    filled = round(width * bounded / 100.0)
    return "█" * filled + "░" * (width - filled)


def warehouse_health_command(
    args,
    *,
    service: Optional[WarehouseMetricsService] = None,
    session_factory=SessionLocal,
) -> int:
    from app.cli_commands.warehouse import _read_catalog

    try:
        catalog_html = _read_catalog(args.catalog)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    db = session_factory()

    try:
        metrics = (service or WarehouseMetricsService()).collect(
            db,
            root=args.root,
            catalog_html=catalog_html,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print()
    print("=" * 76)
    print("DartsEdge Warehouse Health")
    print("=" * 76)
    print(f"Health            : {'healthy' if metrics.healthy else 'attention required'}")
    print(f"Root              : {metrics.root}")
    print()
    print("Series")
    print("-" * 76)
    print(
        _percentage_bar(metrics.series_completion_percentage)
        + f" {metrics.series_completion_percentage:.1f}%"
    )
    print(f"Discovered        : {metrics.discovered_series}")
    print(f"Complete          : {metrics.complete_series}")
    print(f"Remaining         : {metrics.remaining_series}")
    print()
    print("Groups")
    print("-" * 76)
    print(f"Discovered        : {metrics.discovered_groups}")
    print(f"Imported          : {metrics.imported_groups}")
    print(f"Ready             : {metrics.ready_groups}")
    print(f"Incomplete        : {metrics.incomplete_groups}")
    print(f"Partial imports   : {metrics.partially_imported_groups}")
    print(f"Errors            : {metrics.error_groups}")
    print()
    print("Matches")
    print("-" * 76)
    print(
        _percentage_bar(metrics.validation_percentage)
        + f" {metrics.validation_percentage:.1f}% validated"
    )
    print(f"Expected          : {metrics.expected_matches}")
    print(f"Validated         : {metrics.validated_matches}")
    print(f"Missing           : {metrics.missing_matches}")
    print(f"Imported mappings : {metrics.imported_fixture_mappings}")
    print()
    print("Database")
    print("-" * 76)
    print(f"Players           : {metrics.database_players}")
    print(f"Matches           : {metrics.database_matches}")
    print(f"Performances      : {metrics.database_performances}")
    print()
    print("Runner")
    print("-" * 76)
    print(
        _percentage_bar(metrics.runner_completion_percentage)
        + f" {metrics.runner_completion_percentage:.1f}%"
    )
    print(f"Status            : {metrics.runner_status}")
    print(f"Processed         : {metrics.runner_processed_matches}")
    print(f"Remaining         : {metrics.runner_remaining_matches}")
    print(f"Total             : {metrics.runner_total_matches}")
    print(f"Current series    : {metrics.runner_current_series or '—'}")
    print(f"Current week      : {metrics.runner_current_week or '—'}")
    print(f"Current group     : {metrics.runner_current_group or '—'}")
    print(f"Current match     : {metrics.runner_current_match_id or '—'}")
    print(f"Last message      : {metrics.runner_last_message}")

    if metrics.runner_last_error:
        print(f"Last error        : {metrics.runner_last_error}")

    print("=" * 76)
    return 0 if metrics.healthy else 1


def register_warehouse_health_command(warehouse_commands) -> None:
    health = warehouse_commands.add_parser(
        "health",
        help="Show read-only warehouse health and progress metrics.",
    )
    health.add_argument(
        "--root",
        default="~/Documents/DartsEdge/Imports",
        help="Historical import root.",
    )
    health.add_argument(
        "--catalog",
        required=True,
        help="Master catalogue HTML file.",
    )
    health.set_defaults(func=warehouse_health_command)
