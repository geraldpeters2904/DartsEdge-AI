import shutil
import tempfile
import unittest
from pathlib import Path

from app.services.modus_folder_service import ModusFolderImportService


FIXTURES = Path("tests/fixtures")


class ModusFolderImportServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = ModusFolderImportService()

    def test_complete_folder_is_ready(self):
        manifest = self.service.inspect(FIXTURES / "modus_folder_complete")
        self.assertTrue(manifest.ready)
        self.assertEqual(manifest.expected_match_ids, [18195, 18196])
        self.assertEqual(manifest.validated_match_ids, [18195, 18196])
        self.assertEqual(manifest.ignored_files, ["notes.txt"])

    def test_incomplete_folder_reports_missing_page(self):
        manifest = self.service.inspect(FIXTURES / "modus_folder_incomplete")
        self.assertFalse(manifest.ready)
        self.assertEqual(manifest.missing_match_ids, [18196])

    def test_missing_results_page_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "match_18195.html").write_text("<html></html>")
            manifest = self.service.inspect(folder)
        self.assertFalse(manifest.ready)
        self.assertIsNone(manifest.results_file)

    def test_unexpected_match_page_blocks_import(self):
        with tempfile.TemporaryDirectory() as folder:
            source = FIXTURES / "modus_folder_complete"
            for item in source.iterdir():
                shutil.copy(item, folder)
            shutil.copy(source / "match_18195.html", Path(folder) / "match_99999.html")
            manifest = self.service.inspect(folder)
        self.assertEqual(manifest.unexpected_match_ids, [99999])
        self.assertFalse(manifest.ready)

    def test_invalid_html_filename_blocks_import(self):
        with tempfile.TemporaryDirectory() as folder:
            source = FIXTURES / "modus_folder_complete"
            for item in source.iterdir():
                shutil.copy(item, folder)
            Path(folder, "bad.html").write_text("<html></html>")
            manifest = self.service.inspect(folder)
        self.assertEqual(manifest.invalid_files, ["bad.html"])
        self.assertFalse(manifest.ready)

    def test_player_mismatch_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            source = FIXTURES / "modus_folder_complete"
            for item in source.iterdir():
                shutil.copy(item, folder)
            path = Path(folder) / "match_18195.html"
            path.write_text(path.read_text().replace("Derek Coulson", "Wrong Player", 1))
            manifest = self.service.inspect(folder)
        self.assertFalse(manifest.ready)
        self.assertTrue(any(i.code == "match_validation_failed" for i in manifest.issues))

    def test_nonexistent_folder_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.service.inspect("/path/that/does/not/exist")

    def test_manifest_serialises(self):
        payload = self.service.inspect(
            FIXTURES / "modus_folder_complete"
        ).to_dict()
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["validated_count"], 2)


if __name__ == "__main__":
    unittest.main()
