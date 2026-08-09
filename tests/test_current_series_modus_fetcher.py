import unittest

from app.services.current_series_modus_fetcher import (
    CURRENT_GROUPS,
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
