import unittest
from pathlib import Path

from app.services.modus_canonical_builder import (
    ModusCanonicalBuilder,
)


FINAL_FOLDER = Path(
    "/Users/geraldpeters/Documents/DartsEdge/Imports/"
    "Series_14/Week_01/Final"
)


class ModusZeroZeroPlaceholderTests(unittest.TestCase):
    def test_final_build_excludes_zero_zero_placeholders(self):
        if not FINAL_FOLDER.is_dir():
            self.skipTest(
                "Real Series 14 Final capture folder is unavailable."
            )

        build = ModusCanonicalBuilder().build(
            FINAL_FOLDER
        )

        fixture_ids = {
            fixture.external_id
            for fixture in build.fixtures
        }
        result_ids = {
            result.match_external_id
            for result in build.results
        }

        self.assertEqual(len(build.fixtures), 7)
        self.assertEqual(len(build.results), 7)
        self.assertEqual(len(build.statistics), 14)
        self.assertTrue(build.ready)

        self.assertNotIn(
            "modus:match:17042",
            fixture_ids,
        )
        self.assertNotIn(
            "modus:match:17046",
            fixture_ids,
        )
        self.assertNotIn(
            "modus:match:17042",
            result_ids,
        )
        self.assertNotIn(
            "modus:match:17046",
            result_ids,
        )


if __name__ == "__main__":
    unittest.main()
