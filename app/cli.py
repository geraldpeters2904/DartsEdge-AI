from __future__ import annotations

import argparse

from app.cli_commands.feature import (
    feature_player_command,
    register_feature_commands,
)
from app.cli_commands.model import (
    model_backtest_command,
    model_compare_command,
    model_laboratory_command,
    register_model_commands,
)
from app.cli_commands.warehouse import (
    DEFAULT_ROOT,
    _format_status,
    _read_catalog,
    register_warehouse_commands,
    warehouse_status_command,
    warehouse_sync_all_command,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description=(
            "DartsEdge application command line interface."
        ),
    )

    commands = parser.add_subparsers(
        dest="command"
    )

    register_warehouse_commands(commands)
    register_model_commands(commands)
    register_feature_commands(commands)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return int(args.func(args))


__all__ = [
    "DEFAULT_ROOT",
    "_format_status",
    "_read_catalog",
    "build_parser",
    "feature_player_command",
    "main",
    "model_backtest_command",
    "model_compare_command",
    "model_laboratory_command",
    "warehouse_status_command",
    "warehouse_sync_all_command",
]


if __name__ == "__main__":
    raise SystemExit(main())
