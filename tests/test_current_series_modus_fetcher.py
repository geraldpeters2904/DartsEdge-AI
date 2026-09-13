import unittest

from app.services.current_series_modus_fetcher import (
    CURRENT_GROUPS,
    CurrentModusTarget,
    _discover_targets,
    _targets_from_catalog,
)


HTML = """
<html>
<select id="seriesSelect">
  <option value="14">Series 14</option>
  <option value="15" selected>Series 15</option>
</select>
<select id="weekSelect">
  <option value="177">Week 12</option>
  <option value="178" selected>Week 13</option>
</select>
<button class="active">Group A</button>
</html>
"""


class CurrentSeriesModusFetcherTests(
    unittest.TestCase
):
    def test_discovery_timeout_does_not_block_other_groups(
        self,
    ):
        calls = []

        class Discovery:
            def discover(
                self,
                db,
                *,
                series_id,
                week_id,
                group,
            ):
                calls.append(group)

                if group == "Group C":
                    raise TimeoutError(
                        "future group unavailable"
                    )

        targets = (
            CurrentModusTarget(
                series_id=15,
                week_id=178,
                group="Group A",
            ),
            CurrentModusTarget(
                series_id=15,
                week_id=178,
                group="Group B",
            ),
            CurrentModusTarget(
                series_id=15,
                week_id=178,
                group="Group C",
            ),
            CurrentModusTarget(
                series_id=15,
                week_id=178,
                group="Final",
            ),
        )

        _discover_targets(
            Discovery(),
            object(),
            targets,
        )

        self.assertEqual(
            calls,
            [
                "Group A",
                "Group B",
                "Group C",
                "Final",
            ],
        )

    def test_empty_fixture_group_does_not_block_other_groups(
        self,
    ):
        calls = []

        class Discovery:
            def discover(
                self,
                db,
                *,
                series_id,
                week_id,
                group,
            ):
                calls.append(group)

                if group == "Final":
                    raise ValueError(
                        "No MODUS fixture cards were found."
                    )

        targets = tuple(
            CurrentModusTarget(
                series_id=15,
                week_id=178,
                group=group,
            )
            for group in CURRENT_GROUPS
        )

        _discover_targets(
            Discovery(),
            object(),
            targets,
        )

        self.assertEqual(
            calls,
            list(CURRENT_GROUPS),
        )

    def test_other_value_error_is_not_hidden(
        self,
    ):
        class Discovery:
            def discover(
                self,
                db,
                *,
                series_id,
                week_id,
                group,
            ):
                raise ValueError(
                    "unexpected parser failure"
                )

        targets = (
            CurrentModusTarget(
                series_id=15,
                week_id=178,
                group="Group A",
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "unexpected parser failure",
        ):
            _discover_targets(
                Discovery(),
                object(),
                targets,
            )

    def test_targets_selected_current_series_week(
        self,
    ):
        targets = (
            _targets_from_catalog(
                HTML
            )
        )

        self.assertEqual(
            len(targets),
            4,
        )

        self.assertEqual(
            {
                item.series_id
                for item in targets
            },
            {15},
        )

        self.assertEqual(
            {
                item.week_id
                for item in targets
            },
            {178},
        )

        self.assertEqual(
            tuple(
                item.group
                for item in targets
            ),
            CURRENT_GROUPS,
        )


if __name__ == "__main__":
    unittest.main()
