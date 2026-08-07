import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.services.historical_import_manager_service import (
    HistoricalImportManagerService,
)
from app.services.modus_folder_service import (
    ModusFolderImportService,
)


REAL_FINAL = Path(
    "/Users/geraldpeters/Documents/DartsEdge/Imports/"
    "Series_14/Week_01/Final"
)


class HistoricalImportableCountTests(unittest.TestCase):
    def setUp(self):
        self.service = HistoricalImportManagerService()

    def test_ready_folder_is_imported_when_all_importable_matches_exist(self):
        manifest = SimpleNamespace(
            ready=True,
            expected_match_ids=list(range(9)),
            results_file=Path("/tmp/results.html"),
        )

        status = self.service._status(
            manifest,
            imported_count=7,
            importable_count=7,
        )

        self.assertEqual(status, "imported")

    def test_incomplete_partial_folder_stays_partially_imported(self):
        manifest = SimpleNamespace(
            ready=False,
            expected_match_ids=list(range(45)),
            results_file=Path("/tmp/results.html"),
        )

        status = self.service._status(
            manifest,
            imported_count=3,
            importable_count=45,
        )

        self.assertEqual(status, "partially_imported")

    def test_real_final_has_seven_importable_matches(self):
        if not REAL_FINAL.is_dir():
            self.skipTest("Real Series 14 Final folder is unavailable.")

        manifest = ModusFolderImportService().inspect(
            REAL_FINAL
        )

        ids = self.service._importable_match_ids(manifest)

        self.assertEqual(len(ids), 7)
        self.assertNotIn(17042, ids)
        self.assertNotIn(17046, ids)


if __name__ == "__main__":
    unittest.main()
