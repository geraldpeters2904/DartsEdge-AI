from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from typing import Optional

from app.services.historical_archive_plan_service import (
    HistoricalArchivePlanService,
)
from app.cli_commands.warehouse_health import (
    register_warehouse_health_command,
    warehouse_health_command,
)
from app.services.warehouse_manager_runner import (
    WarehouseManagerRunner,
    WarehouseManagerRunnerStatus,
)


DEFAULT_ROOT = Path(
    "~/Documents/DartsEdge/Imports"
).expanduser()


def _read_catalog(path_value: str) -> str:
    path = Path(
        path_value
    ).expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError(
            "Master catalogue file does not exist: "
            f"{path}"
        )

    text = path.read_text(
        encoding="utf-8"
    )

    if not text.strip():
        raise ValueError(
            "Master catalogue file is blank: "
            f"{path}"
        )

    return text


def _format_status(
    status: WarehouseManagerRunnerStatus,
) -> str:
    lines = [
        "",
        "=" * 68,
        "DartsEdge Warehouse Manager",
        "=" * 68,
        (
            "Running           : "
            f"{'yes' if status.running else 'no'}"
        ),
        f"Cycles            : {status.cycles}",
        (
            "Prepared cycles   : "
            f"{status.prepared_cycles}"
        ),
        (
            "Captured cycles   : "
            f"{status.captured_cycles}"
        ),
        (
            "Imported cycles   : "
            f"{status.imported_cycles}"
        ),
        (
            "Completed series  : "
            f"{status.completed_series}"
        ),
        (
            "Remaining series  : "
            f"{status.remaining_series}"
        ),
        (
            "Current series    : "
            f"{status.current_series or '—'}"
        ),
        (
            "Last action       : "
            f"{status.last_action or '—'}"
        ),
        (
            "Last message      : "
            f"{status.last_message}"
        ),
    ]

    if status.last_error:
        lines.append(
            "Last error        : "
            f"{status.last_error}"
        )

    lines.append("=" * 68)

    return "\n".join(lines)


def warehouse_sync_all_command(
    args,
    *,
    runner: Optional[
        WarehouseManagerRunner
    ] = None,
) -> int:
    runner = (
        runner or WarehouseManagerRunner()
    )

    try:
        catalog_html = _read_catalog(
            args.catalog
        )
    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    root = Path(
        args.root
    ).expanduser().resolve()

    print()
    print(
        "Starting DartsEdge warehouse "
        "synchronisation"
    )
    print(f"Root      : {root}")
    print(
        "Catalogue : "
        f"{Path(args.catalog).expanduser().resolve()}"
    )
    print(
        f"Watch     : {args.watch_folder}"
    )
    print()

    def progress(
        status: WarehouseManagerRunnerStatus,
    ):
        timestamp = datetime.now().strftime(
            "%H:%M:%S"
        )

        print(
            f"{timestamp} | "
            f"action={status.last_action or '—'} | "
            f"series={status.current_series or '—'} | "
            f"cycles={status.cycles} | "
            f"imports={status.imported_cycles} | "
            "remaining_series="
            f"{status.remaining_series} | "
            f"{status.last_message}"
        )

    try:
        status = runner.run_foreground(
            root=root,
            master_catalog_html=(
                catalog_html
            ),
            watch_folder=(
                args.watch_folder
            ),
            progress_callback=progress,
        )
    except KeyboardInterrupt:
        status = runner.stop()
        print()
        print(
            "Warehouse synchronisation "
            "interrupted."
        )
        print(_format_status(status))
        return 130

    print(_format_status(status))

    if status.last_action == "complete":
        return 0

    if status.last_error:
        return 1

    return 0


def warehouse_status_command(
    args,
    *,
    plan_service: Optional[
        HistoricalArchivePlanService
    ] = None,
) -> int:
    plan_service = (
        plan_service
        or HistoricalArchivePlanService()
    )

    try:
        catalog_html = _read_catalog(
            args.catalog
        )
        plan = plan_service.build_plan(
            root=args.root,
            catalog_html=catalog_html,
        )
    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        return 2

    print()
    print("=" * 68)
    print(
        "DartsEdge Historical Archive Status"
    )
    print("=" * 68)
    print(
        f"Root              : {plan.root}"
    )
    print(
        "Discovered series : "
        f"{plan.discovered_series}"
    )
    print(
        "Complete series   : "
        f"{plan.complete_series}"
    )
    print(
        "Remaining series  : "
        f"{plan.remaining_series}"
    )
    print()

    for item in plan.series:
        marker = (
            "✓" if item.complete else "•"
        )

        print(
            f"{marker} "
            f"{item.series_label:<12} "
            f"{item.status:<12} "
            "prepared="
            f"{item.prepared_groups:<3} "
            "complete="
            f"{item.complete_groups:<3} "
            "incomplete="
            f"{item.incomplete_groups:<3}"
        )

    if plan.next_series is not None:
        print()
        print(
            "Next series       : "
            f"{plan.next_series.series_label}"
        )
    else:
        print()
        print("Archive complete.")

    print("=" * 68)

    return 0


def register_warehouse_commands(
    commands,
) -> None:
    warehouse = commands.add_parser(
        "warehouse",
        help="Historical warehouse commands.",
    )
    warehouse_commands = (
        warehouse.add_subparsers(
            dest="warehouse_command"
        )
    )

    sync_all = (
        warehouse_commands.add_parser(
            "sync-all",
            help=(
                "Synchronise every available "
                "MODUS series from newest to "
                "oldest."
            ),
        )
    )
    sync_all.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help=(
            "Historical archive root folder."
        ),
    )
    sync_all.add_argument(
        "--catalog",
        required=True,
        help=(
            "Saved rendered MODUS results HTML "
            "containing the full series catalogue."
        ),
    )
    sync_all.add_argument(
        "--watch-folder",
        default="~/Downloads",
        help=(
            "Folder used by the historical "
            "capture workflow."
        ),
    )
    sync_all.set_defaults(
        func=warehouse_sync_all_command
    )

    status = (
        warehouse_commands.add_parser(
            "status",
            help=(
                "Show newest-to-oldest archive "
                "completion."
            ),
        )
    )
    status.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help=(
            "Historical archive root folder."
        ),
    )
    status.add_argument(
        "--catalog",
        required=True,
        help=(
            "Saved rendered MODUS results HTML "
            "containing the full series catalogue."
        ),
    )
    status.set_defaults(
        func=warehouse_status_command
    )

    register_warehouse_health_command(
        warehouse_commands
    )
