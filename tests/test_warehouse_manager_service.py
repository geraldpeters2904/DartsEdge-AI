import unittest
from dataclasses import dataclass
from pathlib import Path

from app.services.warehouse_manager_service import (
    WarehouseManagerService,
)


ROOT = Path("/tmp/history").resolve()


@dataclass
class FakeSeriesItem:
    series_id: int
    series_label: str


@dataclass
class FakePlan:
    complete: bool
    next_series: object = None


class FakeArchivePlanService:
    def __init__(self, plan):
        self.plan = plan
        self.calls = []

    def build_plan(self, *, root, catalog_html):
        self.calls.append(
            (Path(root), catalog_html)
        )
        return self.plan


@dataclass
class FakeOption:
    value: int
    label: str


@dataclass
class FakeCatalog:
    weeks: tuple
    groups: tuple
    selected_series_id: int


class FakeCatalogService:
    def __init__(self):
        self.selected_series_id = 14
        self.calls = []

    def parse(self, html):
        self.calls.append(html)
        return FakeCatalog(
            weeks=(FakeOption(165, "Week 1"),),
            groups=("Group A",),
            selected_series_id=self.selected_series_id,
        )


class FakeBrowserSession:
    def __init__(self):
        self.goto_calls = []
        self.wait_calls = []
        self.closed = False
        self.page_html = "<html>series</html>"

    def goto(self, url, *, timeout_seconds=30.0):
        self.goto_calls.append(
            (url, timeout_seconds)
        )

    def wait_for(
        self,
        predicate,
        *,
        timeout_seconds=30.0,
        description="browser condition",
    ):
        self.wait_calls.append(
            (timeout_seconds, description)
        )

        if not predicate():
            raise TimeoutError(description)

    def html(self):
        return self.page_html

    def close(self):
        self.closed = True


@dataclass
class FakeSyncResult:
    action: str = "captured"
    message: str = "Captured match 16947."
    continue_running: bool = True
    error: str = None


class FakeSeriesSyncService:
    def __init__(self):
        self.calls = []
        self.result = FakeSyncResult()

    def run_cycle(
        self,
        db,
        *,
        root,
        catalog_html,
        watch_folder,
    ):
        self.calls.append(
            (
                db,
                Path(root),
                catalog_html,
                watch_folder,
            )
        )
        return self.result


class FakeDb:
    def __init__(self):
        self.rolled_back = False

    def rollback(self):
        self.rolled_back = True


class WarehouseManagerServiceTests(
    unittest.TestCase
):
    def build(self, plan):
        self.archive = FakeArchivePlanService(plan)
        self.catalog = FakeCatalogService()
        self.browser = FakeBrowserSession()
        self.sync = FakeSeriesSyncService()

        return WarehouseManagerService(
            archive_plan_service=self.archive,
            series_sync_service=self.sync,
            catalog_service=self.catalog,
            browser_session=self.browser,
            timeout_seconds=5,
        )

    def test_archive_complete_stops_without_browser(self):
        service = self.build(
            FakePlan(complete=True)
        )

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
            master_catalog_html="<html></html>",
        )

        self.assertTrue(result.complete)
        self.assertFalse(result.continue_running)
        self.assertEqual(self.browser.goto_calls, [])
        self.assertEqual(self.sync.calls, [])

    def test_loads_newest_incomplete_series(self):
        current = FakeSeriesItem(
            series_id=14,
            series_label="Series 14",
        )
        service = self.build(
            FakePlan(
                complete=False,
                next_series=current,
            )
        )

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
            master_catalog_html="<html>master</html>",
            watch_folder="~/Downloads",
        )

        self.assertEqual(result.action, "captured")
        self.assertEqual(result.current_series, current)
        self.assertTrue(result.continue_running)
        self.assertEqual(
            self.browser.goto_calls[0][0],
            (
                "https://modussuperseries.com/results?"
                "series_id=14&week_id=165&group=Group+A"
            ),
        )
        self.assertEqual(len(self.sync.calls), 1)

    def test_wrong_loaded_series_times_out(self):
        current = FakeSeriesItem(
            series_id=14,
            series_label="Series 14",
        )
        service = self.build(
            FakePlan(
                complete=False,
                next_series=current,
            )
        )
        self.catalog.selected_series_id = 13
        db = FakeDb()

        result = service.run_cycle(
            db,
            root=ROOT,
            master_catalog_html="<html>master</html>",
        )

        self.assertEqual(result.action, "error")
        self.assertIn("Series 14", result.error)
        self.assertTrue(db.rolled_back)

    def test_sync_error_is_propagated(self):
        current = FakeSeriesItem(
            series_id=14,
            series_label="Series 14",
        )
        service = self.build(
            FakePlan(
                complete=False,
                next_series=current,
            )
        )
        self.sync.result = FakeSyncResult(
            action="blocked",
            message="Validation blocked.",
            continue_running=False,
            error="Missing page.",
        )

        result = service.run_cycle(
            FakeDb(),
            root=ROOT,
            master_catalog_html="<html>master</html>",
        )

        self.assertEqual(result.action, "blocked")
        self.assertFalse(result.continue_running)
        self.assertEqual(result.error, "Missing page.")

    def test_close_closes_browser(self):
        service = self.build(
            FakePlan(complete=True)
        )

        service.close()

        self.assertTrue(self.browser.closed)


if __name__ == "__main__":
    unittest.main()
