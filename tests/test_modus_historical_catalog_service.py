import unittest

from app.services.modus_historical_catalog_service import (
    ModusHistoricalCatalogService,
)


HTML = """
<!doctype html>
<html>
<body>
<select id="seriesSelect">
  <option value="13">Series 13</option>
  <option value="14" selected>Series 14</option>
  <option value="15">Series 15</option>
</select>

<button onclick="changeGroup('Group A')" class="active">
  Group A
</button>
<button onclick="changeGroup('Group B')">
  Group B
</button>
<button onclick="changeGroup('Group C')">
  Group C
</button>
<button onclick="changeGroup('Final')">
  Final
</button>
<button onclick="changeGroup('Averages')">
  Averages
</button>

<select id="weekSelect">
  <option value="165" selected>Week 1</option>
  <option value="166">Week 2</option>
  <option value="167">Week 3</option>
</select>
</body>
</html>
"""


class ModusHistoricalCatalogServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = ModusHistoricalCatalogService()

    def test_parses_series_weeks_and_groups(self):
        catalog = self.service.parse(HTML)

        self.assertEqual(
            [item.value for item in catalog.series],
            [13, 14, 15],
        )
        self.assertEqual(
            [item.value for item in catalog.weeks],
            [165, 166, 167],
        )
        self.assertEqual(
            catalog.groups,
            (
                "Group A",
                "Group B",
                "Group C",
                "Final",
            ),
        )

    def test_parses_selected_scope(self):
        catalog = self.service.parse(HTML)

        self.assertTrue(catalog.ready)
        self.assertEqual(
            catalog.selected_series_id,
            14,
        )
        self.assertEqual(
            catalog.selected_week_id,
            165,
        )
        self.assertEqual(
            catalog.selected_group,
            "Group A",
        )

    def test_builds_targets_for_every_week_and_group(self):
        targets = (
            self.service.targets_for_selected_series(
                HTML
            )
        )

        self.assertEqual(len(targets), 12)
        self.assertEqual(
            targets[0].source_url,
            (
                "https://modussuperseries.com/results?"
                "series_id=14&week_id=165&group=Group+A"
            ),
        )
        self.assertEqual(
            targets[-1].source_url,
            (
                "https://modussuperseries.com/results?"
                "series_id=14&week_id=167&group=Final"
            ),
        )

    def test_builds_selected_target(self):
        target = self.service.selected_target(HTML)

        self.assertEqual(target.series_id, 14)
        self.assertEqual(target.week_id, 165)
        self.assertEqual(target.group, "Group A")

    def test_averages_is_not_a_capture_target(self):
        catalog = self.service.parse(HTML)

        self.assertNotIn(
            "Averages",
            catalog.groups,
        )

    def test_blank_html_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "must not be blank",
        ):
            self.service.parse(" ")

    def test_missing_series_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "No MODUS series options",
        ):
            self.service.parse(
                '<select id="weekSelect">'
                '<option value="1" selected>Week 1</option>'
                '</select>'
                '<button class="active">Group A</button>'
            )

    def test_unsupported_buttons_are_ignored(self):
        html = HTML.replace(
            "</body>",
            (
                '<button onclick="changeGroup(\'Other\')">'
                "Other</button></body>"
            ),
        )

        catalog = self.service.parse(html)

        self.assertNotIn("Other", catalog.groups)


if __name__ == "__main__":
    unittest.main()
