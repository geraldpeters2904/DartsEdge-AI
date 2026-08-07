import json
import tempfile
import unittest
from pathlib import Path

from app.services.historical_archive_plan_service import (
    HistoricalArchivePlanService,
)
from app.services.modus_historical_catalog_service import (
    ModusCatalogOption,
    ModusHistoricalCatalog,
)


class FakeCatalogService:
    def parse(self, html):
        return ModusHistoricalCatalog(
            series=(
                ModusCatalogOption(
                    value=103,
                    label="Series 13",
                ),
                ModusCatalogOption(
                    value=205,
                    label="Series 14",
                    selected=True,
                ),
                ModusCatalogOption(
                    value=17,
                    label="Series 1",
                ),
            ),
            weeks=(
                ModusCatalogOption(
                    value=1,
                    label="Week 1",
                    selected=True,
                ),
            ),
            groups=("Group A",),
            selected_series_id=205,
            selected_week_id=1,
            selected_group="Group A",
        )


class HistoricalArchivePlanServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = HistoricalArchivePlanService(
            catalog_service=FakeCatalogService()
        )

    def write_session(
        self,
        root,
        *,
        series_id,
        group,
        complete,
    ):
        folder = (
            Path(root)
            / f"Series_{series_id}"
            / "Week_01"
            / group
        )
        folder.mkdir(parents=True, exist_ok=True)
        (
            folder / ".modus_capture_session.json"
        ).write_text(
            json.dumps(
                {
                    "complete": complete,
                    "missing_count": 0 if complete else 12,
                }
            ),
            encoding="utf-8",
        )

    def test_orders_series_newest_to_oldest(self):
        with tempfile.TemporaryDirectory() as root:
            plan = self.service.build_plan(
                root=root,
                catalog_html="<html></html>",
            )

        self.assertEqual(
            [item.series_label for item in plan.series],
            ["Series 14", "Series 13", "Series 1"],
        )

    def test_does_not_assume_sequential_ids(self):
        with tempfile.TemporaryDirectory() as root:
            plan = self.service.build_plan(
                root=root,
                catalog_html="<html></html>",
            )

        self.assertEqual(
            [item.series_id for item in plan.series],
            [205, 103, 17],
        )

    def test_selects_latest_incomplete_series(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_session(
                root,
                series_id=205,
                group="Group_A",
                complete=True,
            )
            self.write_session(
                root,
                series_id=103,
                group="Group_A",
                complete=False,
            )

            plan = self.service.build_plan(
                root=root,
                catalog_html="<html></html>",
            )

        self.assertEqual(
            plan.next_series.series_label,
            "Series 13",
        )
        self.assertEqual(plan.complete_series, 1)
        self.assertEqual(plan.remaining_series, 2)

    def test_unstarted_latest_series_is_next(self):
        with tempfile.TemporaryDirectory() as root:
            plan = self.service.build_plan(
                root=root,
                catalog_html="<html></html>",
            )

        self.assertEqual(
            plan.next_series.series_label,
            "Series 14",
        )
        self.assertEqual(
            plan.next_series.status,
            "not_started",
        )

    def test_marks_archive_complete(self):
        with tempfile.TemporaryDirectory() as root:
            for series_id in (205, 103, 17):
                self.write_session(
                    root,
                    series_id=series_id,
                    group="Group_A",
                    complete=True,
                )

            plan = self.service.build_plan(
                root=root,
                catalog_html="<html></html>",
            )

        self.assertTrue(plan.complete)
        self.assertIsNone(plan.next_series)
        self.assertEqual(plan.complete_series, 3)


if __name__ == "__main__":
    unittest.main()
