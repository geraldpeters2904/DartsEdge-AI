import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path

from app.cli import (
    build_parser,
    main,
    warehouse_status_command,
    warehouse_sync_all_command,
)


@dataclass
class FakeRunnerStatus:
    root: str = "/tmp/history"
    running: bool = False
    started_at: str = None
    updated_at: str = None
    cycles: int = 3
    prepared_cycles: int = 1
    captured_cycles: int = 1
    imported_cycles: int = 1
    completed_series: int = 14
    remaining_series: int = 0
    current_series: str = None
    last_action: str = "complete"
    last_message: str = "Archive complete."
    last_error: str = None


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.status_value = FakeRunnerStatus()

    def run_foreground(
        self,
        *,
        root,
        master_catalog_html,
        watch_folder,
        progress_callback,
    ):
        self.calls.append(
            (
                Path(root),
                master_catalog_html,
                watch_folder,
            )
        )
        progress_callback(self.status_value)
        return self.status_value

    def stop(self):
        return self.status_value


@dataclass
class FakeSeriesItem:
    series_label: str
    status: str
    prepared_groups: int
    complete_groups: int
    incomplete_groups: int
    complete: bool


@dataclass
class FakePlan:
    root: Path
    discovered_series: int
    complete_series: int
    remaining_series: int
    series: tuple
    next_series: object


class FakePlanService:
    def __init__(self):
        self.calls = []

    def build_plan(self, *, root, catalog_html):
        self.calls.append(
            (Path(root), catalog_html)
        )
        series_14 = FakeSeriesItem(
            series_label="Series 14",
            status="complete",
            prepared_groups=52,
            complete_groups=52,
            incomplete_groups=0,
            complete=True,
        )
        series_13 = FakeSeriesItem(
            series_label="Series 13",
            status="not_started",
            prepared_groups=0,
            complete_groups=0,
            incomplete_groups=0,
            complete=False,
        )
        return FakePlan(
            root=Path(root),
            discovered_series=14,
            complete_series=1,
            remaining_series=13,
            series=(series_14, series_13),
            next_series=series_13,
        )


class AppCliTests(unittest.TestCase):
    def write_catalog(self, root):
        path = Path(root) / "catalog.html"
        path.write_text(
            "<html>catalog</html>",
            encoding="utf-8",
        )
        return path

    def test_parser_registers_warehouse_commands(self):
        parser = build_parser()

        args = parser.parse_args([
            "warehouse",
            "status",
            "--catalog",
            "/tmp/catalog.html",
        ])

        self.assertEqual(args.command, "warehouse")
        self.assertEqual(
            args.warehouse_command,
            "status",
        )

    def test_sync_all_runs_foreground_runner(self):
        with tempfile.TemporaryDirectory() as root:
            catalog = self.write_catalog(root)
            runner = FakeRunner()
            args = build_parser().parse_args([
                "warehouse",
                "sync-all",
                "--root",
                root,
                "--catalog",
                str(catalog),
            ])

            output = io.StringIO()

            with redirect_stdout(output):
                code = warehouse_sync_all_command(
                    args,
                    runner=runner,
                )

        self.assertEqual(code, 0)
        self.assertEqual(len(runner.calls), 1)
        self.assertIn(
            "Archive complete.",
            output.getvalue(),
        )

    def test_status_prints_archive_plan(self):
        with tempfile.TemporaryDirectory() as root:
            catalog = self.write_catalog(root)
            args = build_parser().parse_args([
                "warehouse",
                "status",
                "--root",
                root,
                "--catalog",
                str(catalog),
            ])
            output = io.StringIO()

            with redirect_stdout(output):
                code = warehouse_status_command(
                    args,
                    plan_service=FakePlanService(),
                )

        self.assertEqual(code, 0)
        self.assertIn("Series 14", output.getvalue())
        self.assertIn("Series 13", output.getvalue())
        self.assertIn(
            "Next series",
            output.getvalue(),
        )

    def test_missing_catalog_returns_error(self):
        args = build_parser().parse_args([
            "warehouse",
            "status",
            "--catalog",
            "/tmp/does-not-exist.html",
        ])
        error = io.StringIO()

        with redirect_stderr(error):
            code = warehouse_status_command(args)

        self.assertEqual(code, 2)
        self.assertIn("does not exist", error.getvalue())

    def test_main_without_command_prints_help(self):
        output = io.StringIO()

        with redirect_stdout(output):
            code = main([])

        self.assertEqual(code, 0)
        self.assertIn(
            "DartsEdge application",
            output.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
